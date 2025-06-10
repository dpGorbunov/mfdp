import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
import sys
import os

# Добавляем путь к app в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from database.database import get_session
from auth.authenticate import authenticate
from auth.hash_password import HashPassword
from models.user import User
from models.product import Product
from models.department import Department
from models.aisle import Aisle


@pytest.fixture(name="session")
def session_fixture():
    """Создаем тестовую БД в памяти"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Создаем тестовые данные
        _create_test_data(session)
        yield session


def _create_test_data(session: Session):
    """Создаем начальные тестовые данные"""
    # Отделы
    dept1 = Department(id=1, name="Produce")
    dept2 = Department(id=2, name="Dairy")
    session.add_all([dept1, dept2])

    # Проходы
    aisle1 = Aisle(id=1, name="Fresh Vegetables")
    aisle2 = Aisle(id=2, name="Milk and Cheese")
    session.add_all([aisle1, aisle2])

    # Продукты
    product1 = Product(
        id=1,
        name="Organic Banana",
        aisle_id=1,
        department_id=1,
        is_active=True
    )
    product2 = Product(
        id=2,
        name="Greek Yogurt",
        aisle_id=2,
        department_id=2,
        is_active=True
    )
    session.add_all([product1, product2])

    # Тестовый пользователь
    hash_pwd = HashPassword()
    user = User(
        id=1,
        email="test@example.com",
        name="Test User",
        password_hash=hash_pwd.create_hash("password123")
    )
    session.add(user)

    session.commit()


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Создаем тестовый клиент"""

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


@pytest.fixture(name="auth_client")
def auth_client_fixture(session: Session):
    """Создаем авторизованный тестовый клиент"""

    def get_session_override():
        return session

    def authenticate_override():
        return "1"  # ID тестового пользователя

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[authenticate] = authenticate_override

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()