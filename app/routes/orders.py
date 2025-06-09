# app/routes/orders.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from database.database import get_session
from models.product import Product
from models.orders import Order
from models.order_item import OrderItem
from models.recommendation import Recommendation
from models.recommendation import ModelType
from schemas.order import OrderCreate, OrderResponse, OrderConfirmation, OrderItemResponse
from auth.authenticate import authenticate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["orders"])


def get_recommendation_service(session: Session):
    """Фабрика для создания сервиса рекомендаций"""
    try:
        from services.recommendation_service import RecommendationService
        return RecommendationService(session)
    except ImportError as e:
        logger.warning(f"Не удалось загрузить ML движок: {e}")
        return None


@router.post("/", response_model=OrderConfirmation)
async def create_order(
        order_data: OrderCreate,
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Создать новый заказ
    """
    # Проверяем, что все продукты существуют
    product_ids = [item.product_id for item in order_data.items]
    products = session.exec(
        select(Product).where(Product.id.in_(product_ids))
    ).all()

    if len(products) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more products not found"
        )

    # Создаем словарь продуктов для быстрого доступа
    products_dict = {p.id: p for p in products}

    # Создаем заказ
    order = Order(user_id=int(user_id))
    session.add(order)
    session.flush()  # Получаем ID заказа

    # Создаем позиции заказа
    order_items = []
    for item in order_data.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity
        )
        session.add(order_item)
        order_items.append(order_item)

    session.commit()

    # Проверяем количество заказов пользователя
    user_orders_count = session.exec(
        select(func.count(Order.id))
        .where(Order.user_id == int(user_id))
    ).one()

    recommendations_updated = False

    # Обновляем рекомендации после создания заказа
    # Но только если у пользователя есть хотя бы 2 заказа (включая текущий)
    if user_orders_count >= 2:
        try:
            recommendation_service = get_recommendation_service(session)
            if recommendation_service:
                # Инвалидируем кеш
                recommendation_service.invalidate_cache(int(user_id))

                # Если это 2-й или 3-й заказ, переобучаем модель
                if user_orders_count <= 3:
                    logger.info(f"Переобучение модели для пользователя {user_id} (заказ #{user_orders_count})")
                    recommendation_service.retrain_model()

                # Генерируем новые рекомендации
                new_recs = recommendation_service.get_recommendations(
                    user_id=int(user_id),
                    model_type=ModelType.COLLABORATIVE,
                    count=20,  # Генерируем больше
                    use_cache=False
                )

                if new_recs:
                    # Удаляем старые рекомендации
                    deleted = session.query(Recommendation).filter(
                        Recommendation.user_id == int(user_id),
                        Recommendation.model_type == ModelType.COLLABORATIVE
                    ).delete()

                    # Сохраняем новые рекомендации
                    for rec in new_recs:
                        new_rec = Recommendation(
                            user_id=int(user_id),
                            product_id=rec["product_id"],
                            score=rec["score"],
                            model_type=ModelType.COLLABORATIVE
                        )
                        session.add(new_rec)

                    session.commit()
                    recommendations_updated = True
                    logger.info(f"Обновлено {len(new_recs)} рекомендаций для пользователя {user_id}, удалено {deleted}")

        except Exception as e:
            logger.error(f"Не удалось обновить рекомендации: {e}")
            session.rollback()  # Откатываем только изменения рекомендаций
    else:
        logger.info(f"Пользователь {user_id} сделал первый заказ, рекомендации будут доступны после второго заказа")

    # Формируем ответ
    items_response = [
        OrderItemResponse(
            product_id=item.product_id,
            product_name=products_dict[item.product_id].name,
            quantity=item.quantity
        )
        for item in order_items
    ]

    message = f"Заказ #{order.id} успешно создан"
    if user_orders_count == 1:
        message += ". Сделайте еще один заказ для получения персональных рекомендаций!"
    elif recommendations_updated:
        message += ". Рекомендации обновлены!"

    return OrderConfirmation(
        order_id=order.id,
        message=message,
        items=items_response,
        recommendations_updated=recommendations_updated
    )


@router.get("/", response_model=List[OrderResponse])
async def get_user_orders(
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session),
        limit: int = 10
):
    """
    Получить список заказов пользователя
    """
    orders = session.exec(
        select(Order)
        .where(Order.user_id == int(user_id))
        .order_by(Order.created_at.desc())
        .limit(limit)
    ).all()

    result = []
    for order in orders:
        # Получаем позиции заказа с информацией о продуктах
        items = session.exec(
            select(
                OrderItem.product_id,
                OrderItem.quantity,
                Product.name.label("product_name")
            )
            .join(Product, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order.id)
        ).all()

        items_response = [
            OrderItemResponse(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity
            )
            for item in items
        ]

        result.append(OrderResponse(
            id=order.id,
            created_at=order.created_at,
            items=items_response,
            total_items=sum(item.quantity for item in items_response)
        ))

    return result


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
        order_id: int,
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Получить информацию о конкретном заказе
    """
    order = session.exec(
        select(Order)
        .where(Order.id == order_id, Order.user_id == int(user_id))
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Получаем позиции заказа
    items = session.exec(
        select(
            OrderItem.product_id,
            OrderItem.quantity,
            Product.name.label("product_name")
        )
        .join(Product, OrderItem.product_id == Product.id)
        .where(OrderItem.order_id == order.id)
    ).all()

    items_response = [
        OrderItemResponse(
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity
        )
        for item in items
    ]

    return OrderResponse(
        id=order.id,
        created_at=order.created_at,
        items=items_response,
        total_items=sum(item.quantity for item in items_response)
    )