# app/routers/products.py
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select, or_
from database.database import get_session
from schemas.recommendation import ProductDetail
from models.product import Product
from models.department import Department
from models.aisle import Aisle

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=List[ProductDetail])
async def get_products(
        session: Session = Depends(get_session),
        search: Optional[str] = Query(None, description="Поиск по названию"),
        department_id: Optional[int] = Query(None, description="Фильтр по отделу"),
        aisle_id: Optional[int] = Query(None, description="Фильтр по проходу"),
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100)
):
    """
    Получить список продуктов с фильтрацией и поиском
    """
    query = select(
        Product.id,
        Product.name,
        Product.aisle_id,
        Product.department_id,
        Aisle.name.label("aisle_name"),
        Department.name.label("department_name")
    ).join(
        Aisle, Product.aisle_id == Aisle.id
    ).join(
        Department, Product.department_id == Department.id
    ).where(
        Product.is_active == True
    )

    # Поиск по названию
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))

    # Фильтр по отделу
    if department_id:
        query = query.where(Product.department_id == department_id)

    # Фильтр по проходу
    if aisle_id:
        query = query.where(Product.aisle_id == aisle_id)

    # Пагинация
    query = query.offset(skip).limit(limit)

    results = session.exec(query).all()

    return [
        ProductDetail(
            id=r.id,
            name=r.name,
            aisle_id=r.aisle_id,
            department_id=r.department_id,
            aisle_name=r.aisle_name,
            department_name=r.department_name
        ) for r in results
    ]


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(
        product_id: int,
        session: Session = Depends(get_session)
):
    """
    Получить информацию о конкретном продукте
    """
    result = session.exec(
        select(
            Product.id,
            Product.name,
            Product.aisle_id,
            Product.department_id,
            Aisle.name.label("aisle_name"),
            Department.name.label("department_name")
        ).join(
            Aisle, Product.aisle_id == Aisle.id
        ).join(
            Department, Product.department_id == Department.id
        ).where(
            Product.id == product_id,
            Product.is_active == True
        )
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Product not found")

    return ProductDetail(
        id=result.id,
        name=result.name,
        aisle_id=result.aisle_id,
        department_id=result.department_id,
        aisle_name=result.aisle_name,
        department_name=result.department_name
    )


@router.get("/departments/list", response_model=List[dict])
async def get_departments(session: Session = Depends(get_session)):
    """
    Получить список всех отделов
    """
    departments = session.exec(select(Department)).all()
    return [{"id": d.id, "name": d.name} for d in departments]


@router.get("/aisles/list", response_model=List[dict])
async def get_aisles(
        department_id: Optional[int] = Query(None),
        session: Session = Depends(get_session)
):
    """
    Получить список проходов (опционально по отделу)
    """
    query = select(Aisle)

    if department_id:
        # Фильтруем проходы по отделу через продукты
        query = select(Aisle).join(
            Product, Aisle.id == Product.aisle_id
        ).where(
            Product.department_id == department_id
        ).distinct()

    aisles = session.exec(query).all()
    return [{"id": a.id, "name": a.name} for a in aisles]
