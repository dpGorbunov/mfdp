from fastapi.testclient import TestClient


def test_create_order(auth_client: TestClient):
    """Тест создания заказа"""
    order_data = {
        "items": [
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 1}
        ]
    }

    response = auth_client.post("/orders/", json=order_data)
    assert response.status_code == 200

    data = response.json()
    assert "order_id" in data
    assert len(data["items"]) == 2


def test_create_empty_order(auth_client: TestClient):
    """Тест создания пустого заказа"""
    order_data = {"items": []}

    response = auth_client.post("/orders/", json=order_data)
    assert response.status_code == 422  # Validation error


def test_get_user_orders(auth_client: TestClient):
    """Тест получения заказов пользователя"""
    # Сначала создаем заказ
    order_data = {
        "items": [{"product_id": 1, "quantity": 1}]
    }
    auth_client.post("/orders/", json=order_data)

    # Получаем список заказов
    response = auth_client.get("/orders/")
    assert response.status_code == 200

    orders = response.json()
    assert isinstance(orders, list)
    assert len(orders) > 0


def test_unauthorized_order_access(client: TestClient):
    """Тест доступа к заказам без авторизации"""
    response = client.get("/orders/")
    assert response.status_code == 401