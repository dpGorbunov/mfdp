# app/schemas/recommendation.py
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.recommendation import ModelType


class ProductBase(BaseModel):
    """Базовая схема продукта"""
    id: int
    name: str
    aisle_id: int
    department_id: int

    class Config:
        from_attributes = True


class ProductDetail(ProductBase):
    """Детальная информация о продукте"""
    aisle_name: Optional[str]
    department_name: Optional[str]
    times_ordered: Optional[int] = 0


class RecommendationResponse(BaseModel):
    """Схема ответа рекомендации"""
    product_id: int
    product_name: str
    score: float
    model_type: ModelType
    aisle_name: Optional[str]
    department_name: Optional[str]

    class Config:
        from_attributes = True


class OrderHistoryItem(BaseModel):
    """Элемент истории заказов"""
    order_id: int
    created_at: datetime
    products_count: int
    products: List[ProductBase]

    class Config:
        from_attributes = True


class UserPreferences(BaseModel):
    """Предпочтения пользователя"""
    favorite_departments: List[str]
    favorite_aisles: List[str]
    total_orders: int
    total_products_ordered: int
    most_ordered_products: List[ProductDetail]
