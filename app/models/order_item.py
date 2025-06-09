# app/models/order_item.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.orders import Order
    from models.product import Product, ProductRead
else:
    from models.product import Product, ProductRead


class OrderItemBase(SQLModel):
    """Базовая модель элемента заказа"""
    order_id: int = Field(foreign_key="orders.id")
    product_id: int = Field(foreign_key="product.id", index=True)
    quantity: int = Field(default=1, gt=0)


class OrderItem(OrderItemBase, table=True):
    """Модель элемента заказа для БД"""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Связи
    order: Optional["Order"] = Relationship(back_populates="order_items")
    product: Optional["Product"] = Relationship(back_populates="order_items")


class OrderItemRead(OrderItemBase):
    """DTO для чтения элемента заказа"""
    id: int
    product: Optional["ProductRead"] = None
