# app/models/department.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.product import Product


class DepartmentBase(SQLModel):
    """Базовая модель отдела"""
    name: str = Field(max_length=100, unique=True)


class Department(DepartmentBase, table=True):
    """Модель отдела для БД"""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Связи
    products: List["Product"] = Relationship(back_populates="department")


class DepartmentRead(DepartmentBase):
    """DTO для чтения отдела"""
    id: int