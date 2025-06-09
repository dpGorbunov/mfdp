# app/models/orders.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from models.user import User
    from models.order_item import OrderItem, OrderItemRead
else:
    from models.order_item import OrderItem, OrderItemRead

class OrderBase(SQLModel):
    """Базовая модель заказа"""
    user_id: int = Field(foreign_key="users.id", index=True)


class Order(OrderBase, table=True):
    """Модель заказа для БД"""
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связи
    user: Optional["User"] = Relationship(back_populates="orders")
    order_items: List["OrderItem"] = Relationship(back_populates="order")


class OrderRead(OrderBase):
    """DTO для чтения заказа"""
    id: int
    created_at: datetime
    order_items: List["OrderItemRead"] = []