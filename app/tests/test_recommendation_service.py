import pytest
from sqlmodel import Session
from services.recommendation_service import RecommendationService
from models.user import User
from models.orders import Order
from models.order_item import OrderItem


def test_recommendation_service_init(session: Session):
    """Тест инициализации сервиса рекомендаций"""
    service = RecommendationService(session)
    assert service is not None
    assert service.session == session


def test_load_data(session: Session):
    """Тест загрузки данных"""
    # Создаем тестовые заказы
    order = Order(id=1, user_id=1)
    session.add(order)

    order_item = OrderItem(order_id=1, product_id=1, quantity=2)
    session.add(order_item)
    session.commit()

    service = RecommendationService(session)
    stats = service.load_data()

    assert "users" in stats
    assert "products" in stats
    assert stats["users"] >= 1
    assert stats["products"] >= 1


def test_get_popular_products(session: Session):
    """Тест получения популярных товаров"""
    service = RecommendationService(session)

    # Создаем заказы для популярности
    for i in range(3):
        order = Order(id=i + 10, user_id=1)
        session.add(order)
        order_item = OrderItem(order_id=i + 10, product_id=1, quantity=1)
        session.add(order_item)
    session.commit()

    service.load_data()
    popular = service.get_recommendations(
        user_id=999,  # Несуществующий пользователь
        model_type="popular",
        count=5
    )

    assert isinstance(popular, list)
    assert len(popular) > 0