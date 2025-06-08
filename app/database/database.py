# app/database/database.py
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from typing import Generator
import redis
from .config import get_settings
import logging

logger = logging.getLogger(__name__)


def get_database_engine() -> Engine:
    """
    Создание и настройка движка SQLAlchemy.

    Returns:
        Engine: Настроенный движок SQLAlchemy
    """
    settings = get_settings()

    # Настройки пула соединений для production
    if settings.DEBUG:
        # В режиме отладки используем NullPool (без пулинга)
        engine = create_engine(
            url=settings.DATABASE_URL_psycopg,
            echo=True,
            poolclass=NullPool
        )
    else:
        # В production используем пул соединений и отключаем логи SQL
        engine = create_engine(
            url=settings.DATABASE_URL_psycopg,
            echo=False,  # Отключаем вывод SQL запросов
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )

    return engine


def get_redis_client() -> redis.Redis:
    """
    Получение клиента Redis для кеширования.

    Returns:
        redis.Redis: Клиент Redis или None если недоступен
    """
    settings = get_settings()
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        # Проверяем соединение
        client.ping()
        logger.info("Redis подключен успешно")
        return client
    except Exception as e:
        logger.warning(f"Redis недоступен: {e}. Работаем без кеша.")
        return None


# Глобальные экземпляры
engine = get_database_engine()
redis_client = get_redis_client()


def get_session() -> Generator[Session, None, None]:
    """Получение сессии базы данных"""
    with Session(engine) as session:
        yield session
