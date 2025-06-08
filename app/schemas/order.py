# app/schemas/order.py
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    """Схема для создания позиции заказа"""
    product_id: int
    quantity: int = Field(ge=1, default=1)


class OrderCreate(BaseModel):
    """Схема для создания заказа"""
    items: List[OrderItemCreate] = Field(..., min_items=1)


class OrderItemResponse(BaseModel):
    """Схема ответа позиции заказа"""
    product_id: int
    product_name: str
    quantity: int

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """Схема ответа заказа"""
    id: int
    created_at: datetime
    items: List[OrderItemResponse]
    total_items: int

    class Config:
        from_attributes = True


class OrderConfirmation(BaseModel):
    """Схема подтверждения заказа"""
    order_id: int
    message: str
    items: List[OrderItemResponse]
    recommendations_updated: bool = True