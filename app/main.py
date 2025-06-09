# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, recommendations, products, orders
from database.config import get_settings
import logging
import subprocess
import time

# Получаем настройки
settings = get_settings()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Отключаем избыточные логи SQLAlchemy если не в режиме отладки
if not settings.DEBUG:
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

# Создаем приложение
app = FastAPI(
    title="Recommendation System API",
    description="API для системы рекомендаций продуктов",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth)
app.include_router(recommendations)
app.include_router(products)
app.include_router(orders)


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"message": "Welcome to Recommendation System API"}


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger = logging.getLogger(__name__)
    logger.info("Starting Recommendation System API...")

    # Проверяем и инициализируем БД
    try:
        from database.database import engine
        from sqlalchemy import text
        import subprocess
        import time

        # Даем время БД запуститься
        time.sleep(10)

        with engine.connect() as conn:
            # Проверяем существование таблицы product
            result = conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'product')"
            )).scalar()

            if not result:
                logger.info("Database is empty. Starting data import...")
                # Запускаем импорт данных
                subprocess.run([
                    "python", "-m", "database.import_fast", "100"
                ], check=True)
                logger.info("Data import completed successfully!")
            else:
                logger.info("Database already initialized.")

    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        # Не прерываем запуск приложения

    # Пробуем предзагрузить популярные товары
    try:
        from services.recommendation_service import RecommendationService
        from database.database import get_session
        from sqlalchemy import text

        # Проверяем, существует ли таблица product
        with next(get_session()) as session:
            result = session.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'product')"
            )).scalar()

            if result:
                service = RecommendationService(session)
                # Загружаем данные и кешируем популярные товары
                service.load_data()
                logger.info("Популярные товары предзагружены в кеш")
            else:
                logger.warning("Таблицы БД еще не созданы. Пропускаем предзагрузку.")
    except Exception as e:
        logger.warning(f"Не удалось предзагрузить популярные товары: {e}")