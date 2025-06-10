from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """Тест проверки здоровья сервиса"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_root_endpoint(client: TestClient):
    """Тест корневого эндпоинта"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "Welcome" in response.json()["message"]