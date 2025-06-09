# app/models/user.py
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from models.orders import Order
    from models.recommendation import Recommendation
else:
    from models.orders import Order

class User(SQLModel, table=True):
    """Модель пользователя"""
    __tablename__ = "users"

    # Первичный ключ - пусть база сама генерирует ID
    id: Optional[int] = Field(default=None, primary_key=True)

    # Основные поля
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None, max_length=255)

    # Статус и временные метки
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Связи
    orders: List["Order"] = Relationship(back_populates="user")
    recommendations: List["Recommendation"] = Relationship(back_populates="user")