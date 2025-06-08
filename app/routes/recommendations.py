# app/routes/recommendations.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from app.database.database import get_session
from app.models.product import Product
from app.models.orders import Order
from app.models.order_item import OrderItem
from app.models.recommendation import Recommendation
from app.models.department import Department
from app.models.aisle import Aisle
from app.models.recommendation import ModelType
from app.schemas.recommendation import (
    RecommendationResponse,
    OrderHistoryItem,
    UserPreferences,
    ProductBase,
    ProductDetail
)
from app.auth.authenticate import authenticate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def get_recommendation_service(session: Session):
    """Фабрика для создания сервиса рекомендаций"""
    try:
        from app.services.recommendation_service import RecommendationService
        return RecommendationService(session)
    except ImportError as e:
        logger.warning(f"Не удалось загрузить ML движок: {e}")
        return None


@router.get("/", response_model=List[RecommendationResponse])
async def get_recommendations(
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session),
        model_type: Optional[ModelType] = Query(None, description="Тип модели рекомендаций"),
        limit: int = Query(10, ge=1, le=50, description="Количество рекомендаций"),
        exclude_popular: bool = Query(False, description="Исключить популярные товары из персональных рекомендаций")
):
    """
    Получить персонализированные рекомендации для текущего пользователя
    """
    user_id_int = int(user_id)

    # Сначала получаем популярные товары (они нужны для исключения)
    popular_product_ids = []
    if exclude_popular and model_type == ModelType.COLLABORATIVE:
        # Получаем ID популярных товаров
        popular_query = session.exec(
            select(Product.id)
            .join(OrderItem, Product.id == OrderItem.product_id)
            .group_by(Product.id)
            .order_by(func.count(OrderItem.id).desc())
            .limit(50)  # Берем топ-50 популярных
        ).all()

        popular_product_ids = list(popular_query)
        print(f"[DEBUG] Found {len(popular_product_ids)} popular products to exclude")

    # Для collaborative рекомендаций
    if model_type == ModelType.COLLABORATIVE:
        # Строим запрос
        query = select(
            Recommendation.product_id,
            Recommendation.score,
            Recommendation.model_type,
            Product.name.label("product_name"),
            Aisle.name.label("aisle_name"),
            Department.name.label("department_name")
        ).join(
            Product, Recommendation.product_id == Product.id
        ).join(
            Aisle, Product.aisle_id == Aisle.id
        ).join(
            Department, Product.department_id == Department.id
        ).where(
            Recommendation.user_id == user_id_int,
            Recommendation.model_type == ModelType.COLLABORATIVE
        )

        # ИСКЛЮЧАЕМ популярные товары
        if exclude_popular and popular_product_ids:
            query = query.where(~Recommendation.product_id.in_(popular_product_ids))

        query = query.order_by(Recommendation.score.desc()).limit(limit * 2)  # Берем больше для запаса

        results = session.exec(query).all()

        print(f"[DEBUG] Found {len(results)} collaborative recommendations after filtering")

        # Если после фильтрации мало рекомендаций, добавляем из оставшихся
        if len(results) < limit:
            # Получаем дополнительные рекомендации, исключая уже выбранные
            already_selected = [r.product_id for r in results]
            exclude_ids = popular_product_ids + already_selected

            additional_query = select(
                Recommendation.product_id,
                Recommendation.score,
                Recommendation.model_type,
                Product.name.label("product_name"),
                Aisle.name.label("aisle_name"),
                Department.name.label("department_name")
            ).join(
                Product, Recommendation.product_id == Product.id
            ).join(
                Aisle, Product.aisle_id == Aisle.id
            ).join(
                Department, Product.department_id == Department.id
            ).where(
                Recommendation.user_id == user_id_int,
                Recommendation.model_type == ModelType.COLLABORATIVE,
                ~Recommendation.product_id.in_(exclude_ids)
            ).order_by(
                Recommendation.score.desc()
            ).limit(limit - len(results))

            additional_results = session.exec(additional_query).all()
            results.extend(additional_results)

        # Ограничиваем до нужного количества
        results = results[:limit]

        if results:
            return [
                RecommendationResponse(
                    product_id=r.product_id,
                    product_name=r.product_name,
                    score=r.score,
                    model_type=r.model_type,
                    aisle_name=r.aisle_name,
                    department_name=r.department_name
                )
                for r in results
            ]

        # Если нет рекомендаций - возвращаем пустой список
        return []

    # Для популярных товаров
    if model_type == ModelType.POPULAR:
        popular_products = session.exec(
            select(
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                Aisle.name.label("aisle_name"),
                Department.name.label("department_name"),
                func.count(OrderItem.id).label("popularity")
            ).select_from(
                Product
            ).join(
                OrderItem, Product.id == OrderItem.product_id
            ).join(
                Aisle, Product.aisle_id == Aisle.id
            ).join(
                Department, Product.department_id == Department.id
            ).group_by(
                Product.id, Product.name, Aisle.name, Department.name
            ).order_by(
                func.count(OrderItem.id).desc()
            ).limit(limit)
        ).all()

        return [
            RecommendationResponse(
                product_id=p.product_id,
                product_name=p.product_name,
                score=1.0 - (idx * 0.05),
                model_type=ModelType.POPULAR,
                aisle_name=p.aisle_name,
                department_name=p.department_name
            )
            for idx, p in enumerate(popular_products)
        ]

    return []


@router.get("/order-history", response_model=List[OrderHistoryItem])
async def get_order_history(
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session),
        limit: int = Query(10, ge=1, le=50)
):
    """
    Получить историю заказов пользователя
    """
    try:
        orders = session.exec(
            select(Order)
            .where(Order.user_id == int(user_id))
            .order_by(Order.created_at.desc())
            .limit(limit)
        ).all()

        result = []
        for order in orders:
            # Получаем товары в заказе
            items = session.exec(
                select(Product)
                .join(OrderItem, Product.id == OrderItem.product_id)
                .where(OrderItem.order_id == order.id)
            ).all()

            result.append(OrderHistoryItem(
                order_id=order.id,
                created_at=order.created_at,
                products_count=len(items),
                products=[
                    ProductBase(
                        id=item.id,
                        name=item.name,
                        aisle_id=item.aisle_id,
                        department_id=item.department_id
                    ) for item in items
                ]
            ))

        return result
    except Exception as e:
        logger.error(f"Ошибка при получении истории заказов: {e}")
        return []


@router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences(
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Получить анализ предпочтений пользователя
    """
    try:
        # Получаем статистику по отделам
        dept_stats = session.exec(
            select(
                Department.name,
                func.count(OrderItem.id).label("count")
            ).select_from(
                Department
            ).join(
                Product, Department.id == Product.department_id
            ).join(
                OrderItem, Product.id == OrderItem.product_id
            ).join(
                Order, OrderItem.order_id == Order.id
            ).where(
                Order.user_id == int(user_id)
            ).group_by(
                Department.name
            ).order_by(
                func.count(OrderItem.id).desc()
            ).limit(5)
        ).all()

        # Получаем статистику по проходам
        aisle_stats = session.exec(
            select(
                Aisle.name,
                func.count(OrderItem.id).label("count")
            ).select_from(
                Aisle
            ).join(
                Product, Aisle.id == Product.aisle_id
            ).join(
                OrderItem, Product.id == OrderItem.product_id
            ).join(
                Order, OrderItem.order_id == Order.id
            ).where(
                Order.user_id == int(user_id)
            ).group_by(
                Aisle.name
            ).order_by(
                func.count(OrderItem.id).desc()
            ).limit(5)
        ).all()

        # Получаем самые заказываемые товары
        most_ordered = session.exec(
            select(
                Product.id,
                Product.name,
                Product.aisle_id,
                Product.department_id,
                Aisle.name.label("aisle_name"),
                Department.name.label("department_name"),
                func.count(OrderItem.id).label("times_ordered")
            ).select_from(
                Product
            ).join(
                OrderItem, Product.id == OrderItem.product_id
            ).join(
                Order, OrderItem.order_id == Order.id
            ).join(
                Aisle, Product.aisle_id == Aisle.id
            ).join(
                Department, Product.department_id == Department.id
            ).where(
                Order.user_id == int(user_id)
            ).group_by(
                Product.id, Product.name, Product.aisle_id,
                Product.department_id, Aisle.name, Department.name
            ).order_by(
                func.count(OrderItem.id).desc()
            ).limit(10)
        ).all()

        # Общая статистика
        total_orders = session.exec(
            select(func.count(Order.id))
            .where(Order.user_id == int(user_id))
        ).one() or 0

        total_products = session.exec(
            select(func.count(OrderItem.id))
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.user_id == int(user_id))
        ).one() or 0

        return UserPreferences(
            favorite_departments=[d.name for d in dept_stats] or ["Не определено"],
            favorite_aisles=[a.name for a in aisle_stats] or ["Не определено"],
            total_orders=total_orders,
            total_products_ordered=total_products,
            most_ordered_products=[
                ProductDetail(
                    id=p.id,
                    name=p.name,
                    aisle_id=p.aisle_id,
                    department_id=p.department_id,
                    aisle_name=p.aisle_name,
                    department_name=p.department_name,
                    times_ordered=p.times_ordered
                ) for p in most_ordered
            ]
        )
    except Exception as e:
        logger.error(f"Ошибка при получении предпочтений пользователя: {e}")
        return UserPreferences(
            favorite_departments=["Не определено"],
            favorite_aisles=["Не определено"],
            total_orders=0,
            total_products_ordered=0,
            most_ordered_products=[]
        )


@router.post("/generate/{model_type}")
async def generate_recommendations(
        model_type: ModelType,
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Запустить генерацию рекомендаций для пользователя с указанной моделью
    """
    recommendation_service = get_recommendation_service(session)

    if not recommendation_service:
        raise HTTPException(
            status_code=503,
            detail="ML движок недоступен"
        )

    try:
        # Проверяем есть ли у пользователя заказы
        user_orders_count = session.exec(
            select(func.count(Order.id))
            .where(Order.user_id == int(user_id))
        ).one() or 0

        if user_orders_count == 0:
            return {
                "message": "У вас пока нет заказов. Сделайте первый заказ для генерации персональных рекомендаций.",
                "status": "no_orders",
                "count": 0,
                "model_type": model_type.value
            }

        # Сначала переобучаем модель для новых пользователей
        logger.info(f"Переобучение модели для генерации рекомендаций пользователя {user_id}")
        retrain_result = recommendation_service.retrain_model()
        logger.info(f"Модель переобучена: {retrain_result}")

        # Генерируем новые рекомендации
        recommendations = recommendation_service.get_recommendations(
            user_id=int(user_id),
            model_type=model_type,
            count=10,
            use_cache=False  # Принудительно перегенерируем
        )

        # ФОРСИРУЕМ СОХРАНЕНИЕ В БД НАПРЯМУЮ
        if recommendations and model_type == ModelType.COLLABORATIVE:
            # Удаляем старые рекомендации
            deleted = session.query(Recommendation).filter(
                Recommendation.user_id == int(user_id),
                Recommendation.model_type == ModelType.COLLABORATIVE
            ).delete()

            # Добавляем новые
            for rec in recommendations:
                new_rec = Recommendation(
                    user_id=int(user_id),
                    product_id=rec["product_id"],
                    score=rec["score"],
                    model_type=ModelType.COLLABORATIVE
                )
                session.add(new_rec)

            session.commit()
            print(f"FORCE SAVED {len(recommendations)} recommendations for user {user_id}, deleted {deleted} old")

        return {
            "message": f"Рекомендации успешно сгенерированы и сохранены!",
            "status": "success",
            "count": len(recommendations),
            "model_type": model_type.value,
            "retrain_info": retrain_result
        }

    except Exception as e:
        logger.error(f"Ошибка при генерации рекомендаций: {e}")
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при генерации рекомендаций: {str(e)}"
        )


@router.post("/retrain")
async def retrain_model(
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Переобучить модель рекомендаций
    """
    recommendation_service = get_recommendation_service(session)

    if not recommendation_service:
        raise HTTPException(
            status_code=503,
            detail="ML движок недоступен"
        )

    try:
        result = recommendation_service.retrain_model()

        return {
            "message": "Модель успешно переобучена",
            "details": result
        }

    except Exception as e:
        logger.error(f"Ошибка при переобучении модели: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при переобучении модели: {str(e)}"
        )


@router.delete("/cache/{target_user_id}")
async def clear_user_cache(
        target_user_id: int,
        user_id: str = Depends(authenticate),
        session: Session = Depends(get_session)
):
    """
    Очистить кеш рекомендаций для пользователя
    """
    recommendation_service = get_recommendation_service(session)

    if not recommendation_service:
        return {
            "message": "ML движок недоступен, кеш не используется",
            "status": "skipped"
        }

    try:
        recommendation_service.invalidate_cache(target_user_id)

        return {
            "message": f"Кеш рекомендаций для пользователя {target_user_id} очищен",
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Ошибка при очистке кеша: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при очистке кеша: {str(e)}"
        )