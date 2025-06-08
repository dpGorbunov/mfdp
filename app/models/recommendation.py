# app/models/recommendation.py
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.product import Product, ProductRead


class ModelType(str, Enum):
    """Типы моделей рекомендаций"""
    POPULAR = "popular"
    TFIDF = "tfidf"
    COLLABORATIVE = "collaborative"


class RecommendationBase(SQLModel):
    """Базовая модель рекомендации"""
    user_id: int = Field(foreign_key="users.id", index=True)
    product_id: int = Field(foreign_key="product.id", index=True)  # Исправлено: было "products.id"
    score: float = Field(ge=0.0, le=1.0)
    model_type: ModelType = Field(index=True)


class Recommendation(RecommendationBase, table=True):
    """Модель рекомендации для БД"""
    __tablename__ = "recommendation"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "model_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связи
    user: Optional["User"] = Relationship(back_populates="recommendations")
    product: Optional["Product"] = Relationship(back_populates="recommendations")


class RecommendationRead(RecommendationBase):
    """DTO для чтения рекомендации"""
    id: int
    created_at: datetime
    product: Optional["ProductRead"] = None


class RecommendationCreate(SQLModel):
    """DTO для создания рекомендаций"""
    user_id: int
    model_type: ModelType = ModelType.COLLABORATIVE
    count: int = Field(default=10, ge=1, le=50)