# app/database/init_db.py
from sqlmodel import SQLModel, Session, select
import pandas as pd
import logging

# Импорт всех моделей для создания таблиц
from app.models.user import User
from app.models.product import Product
from app.models.department import Department
from app.models.aisle import Aisle
from app.models.orders import Order
from app.models.order_item import OrderItem
from app.models.recommendation import Recommendation
from app.database.database import get_database_engine
from app.auth.hash_password import HashPassword

logger = logging.getLogger(__name__)
hash_password = HashPassword()


def init_db(drop_all: bool = False) -> None:
    """
    Инициализация схемы базы данных.

    Args:
        drop_all: Если True, удаляет все таблицы перед созданием
    """
    engine = get_database_engine()

    try:
        if drop_all:
            logger.warning("Удаление всех таблиц...")
            SQLModel.metadata.drop_all(engine)

        logger.info("Создание таблиц...")
        SQLModel.metadata.create_all(engine)

        # Создание начальных данных
        with Session(engine) as session:
            # Проверяем, нужно ли загружать данные
            if session.exec(select(User)).first() is None:
                logger.info("Загрузка начальных данных...")
                load_initial_data(session)

        logger.info("База данных успешно инициализирована")

    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
        raise


def load_initial_data(session: Session) -> None:
    """
    Загрузка начальных данных из CSV файлов.

    Args:
        session: Сессия базы данных
    """
    # Создание тестовых пользователей с паролями
    test_users = [
        User(
            email="admin@example.com",
            name="Admin User",
            password_hash=hash_password.create_hash("admin123")
        ),
        User(
            email="test1@example.com",
            name="Test User 1",
            password_hash=hash_password.create_hash("test123")
        ),
        User(
            email="test2@example.com",
            name="Test User 2",
            password_hash=hash_password.create_hash("test123")
        ),
    ]

    for user in test_users:
        session.add(user)

    # Загрузка данных из CSV (если есть)
    try:
        load_products_from_csv(session, "data/products.csv")
        load_orders_from_csv(session, "data/orders.csv")
    except FileNotFoundError:
        logger.warning("CSV файлы не найдены, используем минимальный набор данных")
        create_sample_data(session)

    session.commit()


def load_products_from_csv(session: Session, filepath: str) -> None:
    """Загрузка продуктов из CSV"""
    df_products = pd.read_csv(filepath)

    # Сначала загружаем отделы и проходы
    departments = df_products[['department_id', 'department']].drop_duplicates()
    for _, row in departments.iterrows():
        dept = Department(id=row['department_id'], name=row['department'])
        session.merge(dept)

    aisles = df_products[['aisle_id', 'aisle']].drop_duplicates()
    for _, row in aisles.iterrows():
        aisle = Aisle(id=row['aisle_id'], name=row['aisle'])
        session.merge(aisle)

    # Загружаем продукты
    for _, row in df_products.iterrows():
        product = Product(
            id=row['product_id'],
            name=row['product_name'],
            aisle_id=row['aisle_id'],
            department_id=row['department_id']
        )
        session.merge(product)

    session.commit()
    logger.info(f"Загружено {len(df_products)} продуктов")


def load_orders_from_csv(session: Session, filepath: str) -> None:
    """Загрузка заказов из CSV"""
    df_orders = pd.read_csv(filepath)

    # Группируем по заказам
    for order_id, group in df_orders.groupby('order_id'):
        # Создаем заказ
        order = Order(
            id=order_id,
            user_id=group.iloc[0]['user_id']
        )
        session.merge(order)

        # Добавляем товары в заказ
        for _, row in group.iterrows():
            order_item = OrderItem(
                order_id=order_id,
                product_id=row['product_id'],
                quantity=1  # По умолчанию
            )
            session.add(order_item)

    session.commit()
    logger.info(f"Загружено {df_orders['order_id'].nunique()} заказов")


def create_sample_data(session: Session) -> None:
    """Создание минимального набора тестовых данных"""
    # Создаем отделы
    dept1 = Department(name="Produce")
    dept2 = Department(name="Dairy")
    session.add_all([dept1, dept2])
    session.flush()

    # Создаем проходы
    aisle1 = Aisle(name="Fresh Vegetables")
    aisle2 = Aisle(name="Packaged Cheese")
    session.add_all([aisle1, aisle2])
    session.flush()

    # Создаем продукты
    products = [
        Product(name="Organic Banana", aisle_id=aisle1.id, department_id=dept1.id),
        Product(name="Organic Avocado", aisle_id=aisle1.id, department_id=dept1.id),
        Product(name="Greek Yogurt", aisle_id=aisle2.id, department_id=dept2.id),
        Product(name="Cheddar Cheese", aisle_id=aisle2.id, department_id=dept2.id),
    ]
    session.add_all(products)
    session.flush()

    # Создаем заказы
    order1 = Order(user_id=1)
    order2 = Order(user_id=2)
    session.add_all([order1, order2])
    session.flush()

    # Добавляем товары в заказы
    order_items = [
        OrderItem(order_id=order1.id, product_id=products[0].id, quantity=2),
        OrderItem(order_id=order1.id, product_id=products[2].id, quantity=1),
        OrderItem(order_id=order2.id, product_id=products[1].id, quantity=3),
        OrderItem(order_id=order2.id, product_id=products[3].id, quantity=1),
    ]
    session.add_all(order_items)

    logger.info("Создан минимальный набор тестовых данных")


def check_db_health(session: Session) -> dict:
    """
    Проверка состояния базы данных.

    Returns:
        dict: Статистика по таблицам
    """
    stats = {}

    try:
        stats['users'] = session.query(User).count()
        stats['products'] = session.query(Product).count()
        stats['orders'] = session.query(Order).count()
        stats['recommendations'] = session.query(Recommendation).count()
        stats['status'] = 'healthy'
    except Exception as e:
        stats['status'] = 'error'
        stats['error'] = str(e)

    return stats