# app/routes/orders.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database.database import get_session
from app.models.product import Product
from app.models.orders import Order
from app.models.order_item import OrderItem
from app.schemas.order import OrderCreate, OrderResponse, OrderConfirmation, OrderItemResponse
from app.services.recommendation_service import RecommendationService
from app.auth.authenticate import authenticate
import logging


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["orders"])


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

    # Инвалидируем кеш рекомендаций после нового заказа
    try:
        from app.services.recommendation_service import RecommendationService
        recommendation_service = RecommendationService(session)
        recommendation_service.invalidate_cache(int(user_id))
    except Exception as e:
        # Не критично, если кеш не очистился
        logger.warning(f"Не удалось очистить кеш рекомендаций: {e}")

    # Формируем ответ
    items_response = [
        OrderItemResponse(
            product_id=item.product_id,
            product_name=products_dict[item.product_id].name,
            quantity=item.quantity
        )
        for item in order_items
    ]

    return OrderConfirmation(
        order_id=order.id,
        message=f"Заказ #{order.id} успешно создан",
        items=items_response,
        recommendations_updated=True
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