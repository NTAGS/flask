import os

os.environ["JWT_SECRET"] = "test-secret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "password"

import pytest

from app import DB, Product, create_app, seed_products


@pytest.fixture()
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "ORDER_QUEUE_ENABLED": False,
        }
    )
    with application.app_context():
        DB.create_all()
        seed_products()
        yield application
        DB.session.remove()
        DB.drop_all()


def login(client):
    response = client.post(
        "/api/v1/login", json={"username": "admin", "password": "password"}
    )
    assert response.status_code == 200
    return response.json["access_token"]


def test_products_seeded(app):
    with app.test_client() as client:
        response = client.get("/api/v1/products")
        assert response.status_code == 200
        assert len(response.json["products"]) == 10
        assert len({p["category"] for p in response.json["products"]}) == 5


def test_login_and_order(app):
    with app.test_client() as client:
        token = login(client)
        product = client.get("/api/v1/products").json["products"][0]
        response = client.post(
            "/api/v1/orders",
            json={"product_id": product["id"], "quantity": 2},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "test-1"},
        )
        assert response.status_code == 201
        assert response.json["quantity"] == 2

        replay = client.post(
            "/api/v1/orders",
            json={"product_id": product["id"], "quantity": 99},
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "test-1"},
        )
        assert replay.status_code == 200
        assert replay.json["order_number"] == response.json["order_number"]


def test_cancel_and_reorder(app):
    with app.test_client() as client:
        token = login(client)
        product = client.get("/api/v1/products").json["products"][0]
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post(
            "/api/v1/orders", json={"product_id": product["id"], "quantity": 1}, headers=headers
        )
        order_number = created.json["order_number"]

        cancelled = client.post(f"/api/v1/orders/{order_number}/cancel", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json["status"] == "CANCELLED"

        reordered = client.post(f"/api/v1/orders/{order_number}/reorder", headers=headers)
        assert reordered.status_code == 201
        assert reordered.json["status"] == "PLACED"
