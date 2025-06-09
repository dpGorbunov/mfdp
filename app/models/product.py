# app/models/product.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.order_item import OrderItem
    from models.recommendation import Recommendation
    from models.department import Department, DepartmentRead
    from models.aisle import Aisle, AisleRead
else:
    from models.aisle import Aisle, AisleRead
    from models.department import Department, DepartmentRead
    from models.recommendation import Recommendation


class ProductBase(SQLModel):
    """Базовая модель товара - только необходимое для рекомендаций"""
    name: str = Field(max_length=255, index=True)
    aisle_id: int = Field(foreign_key="aisle.id")
    department_id: int = Field(foreign_key="department.id")
    is_active: bool = Field(default=True)


class Product(ProductBase, table=True):
    """Модель товара для БД"""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Связи
    aisle: Optional["Aisle"] = Relationship(back_populates="products")
    department: Optional["Department"] = Relationship(back_populates="products")
    order_items: List["OrderItem"] = Relationship(back_populates="product")
    recommendations: List["Recommendation"] = Relationship(back_populates="product")


class ProductRead(ProductBase):
    """DTO для чтения товара"""
    id: int
    aisle: Optional["AisleRead"] = None
    department: Optional["DepartmentRead"] = None
