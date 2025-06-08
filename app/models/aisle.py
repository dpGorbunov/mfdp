# app/models/aisle.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.product import Product


class AisleBase(SQLModel):
    """Базовая модель прохода/категории"""
    name: str = Field(max_length=100, unique=True)


class Aisle(AisleBase, table=True):
    """Модель прохода для БД"""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Связи
    products: List["Product"] = Relationship(back_populates="aisle")


class AisleRead(AisleBase):
    """DTO для чтения прохода"""
    id: int