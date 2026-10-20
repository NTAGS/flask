import os
import signal
import time

from redis import Redis

from app import DB, Order, create_app

app = create_app()
r = Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=5,
)
STOP = False


def stop_handler(signum, frame):
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)


def process(order_number):
    with app.app_context():
        order = Order.query.filter_by(order_number=order_number).first()
        if not order or order.status == "CANCELLED":
            return

        for status in ("CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"):
            if STOP:
                return
            time.sleep(2)
            order = Order.query.filter_by(order_number=order_number).first()
            if not order or order.status == "CANCELLED":
                return
            order.status = status
            DB.session.commit()
            app.logger.info(
                "order_status_changed order=%s status=%s",
                order_number,
                status,
            )


while not STOP:
    try:
        item = r.blpop("order_events", timeout=5)
        if item:
            process(item[1])
    except Exception:
        app.logger.exception("worker_iteration_failed")
        time.sleep(2)
