import json

import logging

import os

import time

import uuid

from functools import wraps



import jwt

from flask import Flask, app, g, has_request_context, jsonify, render_template, request

from flask_sqlalchemy import SQLAlchemy

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from redis import Redis

from sqlalchemy import text



try:

    from opentelemetry import trace

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    from opentelemetry.instrumentation.redis import RedisInstrumentor

    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler

    from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor

    from opentelemetry.sdk.resources import Resource

    from opentelemetry.sdk.trace import TracerProvider

    from opentelemetry.sdk.trace.export import BatchSpanProcessor

except ImportError:  # pragma: no cover - optional at import time

    trace = None





DB = SQLAlchemy()

REQUESTS = Counter("commerce_http_requests_total", "HTTP requests", ["method", "path", "status"])

ORDERS = Counter("commerce_orders_total", "Orders created", ["category"])

REQUEST_LATENCY = Histogram("commerce_http_request_duration_seconds", "HTTP latency", ["method", "path"])



CATEGORIES = {

    "electronics": [("Wireless Headphones", 79.99), ("Smart Watch", 129.99)],

    "home": [("Coffee Maker", 59.99), ("Air Purifier", 149.99)],

    "office": [("Mechanical Keyboard", 89.99), ("4K Monitor", 299.99)],

    "fitness": [("Yoga Mat", 29.99), ("Fitness Tracker", 99.99)],

    "grocery": [("Organic Coffee", 14.99), ("Protein Bars", 24.99)],

}





class Product(DB.Model):

    id = DB.Column(DB.Integer, primary_key=True)

    name = DB.Column(DB.String(160), nullable=False, unique=True)

    category = DB.Column(DB.String(80), nullable=False, index=True)

    price = DB.Column(DB.Numeric(10, 2), nullable=False)

    active = DB.Column(DB.Boolean, default=True, nullable=False)





class Order(DB.Model):

    id = DB.Column(DB.Integer, primary_key=True)

    order_number = DB.Column(DB.String(36), unique=True, nullable=False, index=True)

    username = DB.Column(DB.String(80), nullable=False, index=True)

    product_id = DB.Column(DB.Integer, DB.ForeignKey("product.id"), nullable=False)

    quantity = DB.Column(DB.Integer, nullable=False)

    total = DB.Column(DB.Numeric(10, 2), nullable=False)

    status = DB.Column(DB.String(40), nullable=False, default="PLACED", index=True)

    idempotency_key = DB.Column(DB.String(128), unique=True, nullable=True)

    created_at = DB.Column(DB.DateTime, server_default=DB.func.now(), nullable=False)

    product = DB.relationship("Product")





class JsonFormatter(logging.Formatter):

    def format(self, record):

        payload = {

            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),

            "level": record.levelname,

            "logger": record.name,

            "message": record.getMessage(),

        }

        # if hasattr(g, "request_id"):

        #     payload["request_id"] = g.request_id

        try:

            if has_request_context() and hasattr(g, "request_id"):

                payload["request_id"] = g.request_id

        except RuntimeError:

            pass

        if trace:

            try:

                ctx = trace.get_current_span().get_span_context()

                if ctx.is_valid:

                    payload["trace_id"] = format(ctx.trace_id, "032x")

                    payload["span_id"] = format(ctx.span_id, "016x")

            except Exception:

                pass

        return json.dumps(payload)





def get_redis():

    client = Redis.from_url(

        os.getenv("REDIS_URL", "redis://localhost:6379/0"),

        socket_connect_timeout=1,

        socket_timeout=2,

        decode_responses=True,

    )

    return client





def init_telemetry(app):

    if not trace or not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):

        return



    resource = Resource.create(

        {

            "service.name": os.getenv("OTEL_SERVICE_NAME", "flask-commerce"),

            "deployment.environment": os.getenv("APP_ENV", "dev"),

        }

    )

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT").rstrip("/")



    provider = TracerProvider(resource=resource)

    provider.add_span_processor(

        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", timeout=5))

    )

    trace.set_tracer_provider(provider)



    log_provider = LoggerProvider(resource=resource)

    log_exporter = OTLPLogExporter(
        endpoint=f"{endpoint}/v1/logs",
        timeout=10,
    )

    # Synchronous export for the local POC.
    # This removes batching as a variable while validating the log path.
    log_provider.add_log_record_processor(
        SimpleLogRecordProcessor(log_exporter)
    )

    otel_handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=log_provider,
    )

    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False

    if not any(
        isinstance(handler, LoggingHandler)
        for handler in app.logger.handlers
    ):
        app.logger.addHandler(otel_handler)

    FlaskInstrumentor().instrument_app(app)

    try:

        SQLAlchemyInstrumentor().instrument()

        RedisInstrumentor().instrument()

    except Exception:

        app.logger.debug("telemetry_instrumentation_already_initialized", exc_info=True)





def seed_products():

    if Product.query.count():

        return

    for category, items in CATEGORIES.items():

        for name, price in items:

            DB.session.add(Product(name=name, category=category, price=price))

    DB.session.commit()





def token_required(fn):

    @wraps(fn)

    def wrapper(*args, **kwargs):

        header = request.headers.get("Authorization", "")

        if not header.startswith("Bearer "):

            return jsonify(error="missing bearer token"), 401

        try:

            payload = jwt.decode(

                header[7:], os.environ["JWT_SECRET"], algorithms=["HS256"]

            )

            g.username = payload["sub"]

        except Exception:

            return jsonify(error="invalid token"), 401

        return fn(*args, **kwargs)



    return wrapper





def create_app(test_config=None):

    app = Flask(__name__)

    app.config.update(

        SQLALCHEMY_DATABASE_URI=os.getenv(

            "DATABASE_URL",

            "postgresql+psycopg://commerce:commerce@localhost:5432/commerce",

        ),

        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        ORDER_QUEUE_ENABLED=os.getenv("ORDER_QUEUE_ENABLED", "true").lower() == "true",

    )

    if test_config:

        app.config.update(test_config)

    DB.init_app(app)



    handler = logging.StreamHandler()

    handler.setFormatter(JsonFormatter())

    app.logger.handlers.clear()

    app.logger.addHandler(handler)

    app.logger.setLevel(logging.INFO)

    init_telemetry(app)



    @app.before_request

    def before():

        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        g.started = time.perf_counter()



    @app.after_request

    def after(resp):

        elapsed = time.perf_counter() - g.started

        metric_path = request.url_rule.rule if request.url_rule else request.path

        REQUESTS.labels(request.method, metric_path, str(resp.status_code)).inc()

        REQUEST_LATENCY.labels(request.method, metric_path).observe(elapsed)

        resp.headers["X-Request-ID"] = g.request_id

        return resp



    @app.get("/")

    def home():

        return render_template("index.html")

    @app.get("/health/live")

    def live():

        return {"status": "ok"}



    @app.get("/health/ready")

    def ready():

        try:

            DB.session.execute(text("SELECT 1"))

            get_redis().ping()

            return {"status": "ready"}

        except Exception as exc:

            app.logger.error("readiness_failed: %s", exc)

            return {"status": "not_ready"}, 503



    @app.get("/metrics")

    def metrics():

        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}



    @app.post("/api/v1/login")

    def login():

        data = request.get_json(silent=True) or {}

        if (

            data.get("username") != os.getenv("ADMIN_USERNAME", "admin")

            or data.get("password") != os.getenv("ADMIN_PASSWORD", "password")

        ):

            return {"error": "invalid credentials"}, 401

        return {

            "access_token": jwt.encode(

                {"sub": data["username"], "iat": int(time.time())},

                os.environ["JWT_SECRET"],

                algorithm="HS256",

            ),

            "token_type": "Bearer",

        }



    @app.get("/api/v1/products")

    def products():

        category = request.args.get("category")

        q = Product.query.filter_by(active=True)

        if category:

            q = q.filter_by(category=category)

        return {

            "products": [

                {

                    "id": p.id,

                    "name": p.name,

                    "category": p.category,

                    "price": float(p.price),

                }

                for p in q.order_by(Product.category, Product.id).all()

            ]

        }



    @app.post("/api/v1/orders")

    @token_required

    def create_order():

        data = request.get_json(silent=True) or {}

        pid, qty = data.get("product_id"), data.get("quantity", 1)

        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1 or qty > 100:

            return {"error": "quantity must be 1-100"}, 400



        idempotency_key = request.headers.get("Idempotency-Key")

        if idempotency_key:

            existing = Order.query.filter_by(idempotency_key=idempotency_key).first()

            if existing:

                return order_json(existing), 200



        product = DB.session.get(Product, pid)

        if not product or not product.active:

            return {"error": "product not found"}, 404



        order = Order(

            order_number=str(uuid.uuid4()),

            username=g.username,

            product_id=product.id,

            quantity=qty,

            total=product.price * qty,

            status="PLACED",

            idempotency_key=idempotency_key,

        )

        DB.session.add(order)

        DB.session.commit()



        if app.config["ORDER_QUEUE_ENABLED"]:

            get_redis().rpush("order_events", order.order_number)

        ORDERS.labels(product.category).inc()

        app.logger.info(

            "order_created order=%s product=%s quantity=%s",

            order.order_number,

            product.name,

            qty,

        )

        return order_json(order), 201



    @app.get("/api/v1/orders")

    @token_required

    def list_orders():

        return {

            "orders": [

                order_json(o)

                for o in Order.query.filter_by(username=g.username)

                .order_by(Order.id.desc())

                .all()

            ]

        }



    @app.get("/api/v1/orders/<order_number>")

    @token_required

    def get_order(order_number):

        order = Order.query.filter_by(

            order_number=order_number, username=g.username

        ).first_or_404()

        return order_json(order)



    @app.post("/api/v1/orders/<order_number>/cancel")

    @token_required

    def cancel(order_number):

        order = Order.query.filter_by(

            order_number=order_number, username=g.username

        ).first_or_404()

        if order.status in ("CANCELLED", "SHIPPED", "DELIVERED"):

            return {"error": f"cannot cancel from {order.status}"}, 409

        order.status = "CANCELLED"

        DB.session.commit()

        app.logger.info("order_cancelled order=%s", order.order_number)

        return order_json(order)



    @app.post("/api/v1/orders/<order_number>/reorder")

    @token_required

    def reorder(order_number):

        old = Order.query.filter_by(

            order_number=order_number, username=g.username

        ).first_or_404()

        new = Order(

            order_number=str(uuid.uuid4()),

            username=g.username,

            product_id=old.product_id,

            quantity=old.quantity,

            total=old.total,

            status="PLACED",

        )

        DB.session.add(new)

        DB.session.commit()

        if app.config["ORDER_QUEUE_ENABLED"]:

            get_redis().rpush("order_events", new.order_number)

        app.logger.info(

            "order_reordered old=%s new=%s", old.order_number, new.order_number

        )

        return order_json(new), 201



    return app





def order_json(order):

    return {

        "order_number": order.order_number,

        "product": order.product.name,

        "quantity": order.quantity,

        "total": float(order.total),

        "status": order.status,

        "created_at": order.created_at.isoformat() if order.created_at else None,

    }
