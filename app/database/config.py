# app/database/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Настройки базы данных
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    DB_NAME: str = "recommendations_db"

    # Альтернативные названия для совместимости
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "recommendations_db"

    # RabbitMQ (если используется)
    RABBITMQ_USER: str = "rmuser"
    RABBITMQ_PASS: str = "rmpassword"

    # Настройки Redis для кеширования
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Настройки приложения
    APP_NAME: str = "Recommendation System API"
    APP_DESCRIPTION: str = "API для системы рекомендаций продуктов"
    DEBUG: bool = False
    API_VERSION: str = "1.0.0"

    # Настройки безопасности
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Настройки ML
    MODEL_UPDATE_INTERVAL: int = 3600  # Обновление модели каждый час
    MIN_ORDERS_FOR_TRAINING: int = 100  # Минимум заказов для обучения

    @property
    def DATABASE_URL_asyncpg(self):
        """URL подключения для asyncpg"""
        # Используем альтернативные переменные если основные не заданы
        user = self.DB_USER or self.POSTGRES_USER
        password = self.DB_PASS or self.POSTGRES_PASSWORD
        db_name = self.DB_NAME or self.POSTGRES_DB
        return f'postgresql+asyncpg://{user}:{password}@{self.DB_HOST}:{self.DB_PORT}/{db_name}'

    @property
    def DATABASE_URL_psycopg(self):
        """URL подключения для psycopg"""
        # Используем альтернативные переменные если основные не заданы
        user = self.DB_USER or self.POSTGRES_USER
        password = self.DB_PASS or self.POSTGRES_PASSWORD
        db_name = self.DB_NAME or self.POSTGRES_DB
        return f'postgresql+psycopg://{user}:{password}@{self.DB_HOST}:{self.DB_PORT}/{db_name}'

    @property
    def REDIS_URL(self):
        """URL подключения к Redis"""
        return f'redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}'

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"  # Разрешаем дополнительные поля
    )


@lru_cache()
def get_settings() -> Settings:
    """Получение настроек приложения с кэшированием"""
    return Settings()