from fastapi.testclient import TestClient
from sqlmodel import Session
from models.user import User


def test_register_new_user(client: TestClient):
    """Тест регистрации нового пользователя"""
    user_data = {
        "email": "newuser@example.com",
        "password": "newpassword123",
        "name": "New User"
    }

    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["name"] == user_data["name"]
    assert "id" in data


def test_register_duplicate_user(client: TestClient):
    """Тест регистрации пользователя с существующим email"""
    user_data = {
        "email": "test@example.com",  # Уже существует
        "password": "password123",
        "name": "Duplicate User"
    }

    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_login_valid_credentials(client: TestClient):
    """Тест входа с валидными данными"""
    login_data = {
        "email": "test@example.com",
        "password": "password123"
    }

    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == login_data["email"]


def test_login_invalid_credentials(client: TestClient):
    """Тест входа с невалидными данными"""
    login_data = {
        "email": "test@example.com",
        "password": "wrongpassword"
    }

    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


def test_get_current_user(auth_client: TestClient):
    """Тест получения информации о текущем пользователе"""
    response = auth_client.get("/auth/me")
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


def test_create_test_user(client: TestClient):
    """Тест создания тестового пользователя"""
    response = client.post("/auth/create-test-user")
    assert response.status_code == 200

    # Проверяем, что можем войти
    login_data = {
        "email": "admin@example.com",
        "password": "admin123"
    }
    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 200