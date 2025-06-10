from fastapi.testclient import TestClient


def test_get_recommendations_new_user(auth_client: TestClient):
    """Тест получения рекомендаций для нового пользователя"""
    response = auth_client.get("/recommendations/")
    assert response.status_code == 200

    recommendations = response.json()
    assert isinstance(recommendations, list)


def test_get_popular_products(auth_client: TestClient):
    """Тест получения популярных товаров"""
    response = auth_client.get("/recommendations/?model_type=popular")
    assert response.status_code == 200

    products = response.json()
    assert isinstance(products, list)


def test_get_user_preferences(auth_client: TestClient):
    """Тест получения предпочтений пользователя"""
    response = auth_client.get("/recommendations/preferences")
    assert response.status_code == 200

    data = response.json()
    assert "favorite_departments" in data
    assert "total_orders" in data


def test_generate_recommendations(auth_client: TestClient):
    """Тест генерации рекомендаций"""
    response = auth_client.post("/recommendations/generate/collaborative")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "model_type" in data