# app/routes/orders.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from database.database import get_session
from models.product import Product
from models.orders import Order
from models.order_item import OrderItem
from schemas.order import OrderCreate, OrderResponse, OrderConfirmation, OrderItemResponse
from auth.authenticate import authenticate
import logging
import pika
import json
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["orders"])


def send_recommendation_update_to_queue(user_id: int, order_id: int, ordered_products: List[int]) -> bool:
    """Отправка задачи на асинхронное обновление рекомендаций в RabbitMQ"""
    try:
        credentials = pika.PlainCredentials('rmuser', 'rmpassword')
        parameters = pika.ConnectionParameters(
            host='rabbitmq',
            port=5672,
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue='ml_task_queue')

        task_data = {
            "task_id": str(uuid.uuid4()),
            "task_type": "update_recommendations",
            "user_id": user_id,
            "order_id": order_id,
            "ordered_products": ordered_products,
            "question": f"Update recommendations for user {user_id} after order {order_id}"  # для совместимости
        }

        channel.basic_publish(
            exchange='',
            routing_key='ml_task_queue',
            body=json.dumps(task_data)
        )
        connection.close()
        logger.info(f"Recommendation update task sent for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send to RabbitMQ: {e}")
        return False


@router.post("/", response_model=OrderConfirmation)
async def create_order(
        order_data: OrderCreate,
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Создать новый заказ с асинхронным обновлением рекомендаций
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

    # Отправляем задачу на обновление рекомендаций если у пользователя >= 2 заказов
    recommendations_queued = False
    if user_orders_count >= 2:
        ordered_product_ids = [item.product_id for item in order_items]
        recommendations_queued = send_recommendation_update_to_queue(
            int(user_id),
            order.id,
            ordered_product_ids
        )

        if recommendations_queued:
            logger.info(f"Задача на обновление рекомендаций отправлена в очередь для пользователя {user_id}")
        else:
            logger.warning(f"Не удалось отправить задачу в очередь для пользователя {user_id}")
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
    elif recommendations_queued:
        message += ". Рекомендации обновляются в фоновом режиме!"

    return OrderConfirmation(
        order_id=order.id,
        message=message,
        items=items_response,
        recommendations_updated=False  # Всегда False, т.к. обновление асинхронное
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