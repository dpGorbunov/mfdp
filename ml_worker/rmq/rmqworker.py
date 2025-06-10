# ml_worker/rmq/rmqworker.py
from rmq.rmqconf import RabbitMQConfig
from llm import do_task
import pika
import time
import logging
import json
import os
import sys

# Добавляем путь к модулям приложения
sys.path.insert(0, '/app')

from sqlmodel import Session, create_engine, select, func
from sqlalchemy.pool import NullPool

# Настраиваем общий уровень логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Устанавливаем уровень WARNING для логов pika
logging.getLogger('pika').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Настройки подключения к БД
DATABASE_URL = f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASS', 'postgres')}@{os.getenv('DB_HOST', 'db')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'sa')}"

# Создаем engine для БД
engine = create_engine(DATABASE_URL, poolclass=NullPool)


# Определяем основной класс для обработки ML задач
class MLWorker:
    """
    Рабочий класс для обработки ML задач из очереди RabbitMQ.
    Обеспечивает подключение к очереди и обработку поступающих сообщений.
    """
    # Константы класса
    MAX_RETRIES = 3
    RETRY_DELAY = 0.5

    def __init__(self, config: RabbitMQConfig):
        """
        Инициализация обработчика с заданной конфигурацией.

        Args:
            config: Объект конфигурации RabbitMQ
        """
        # Сохраняем конфигурацию
        self.config = config
        # Инициализируем соединение как None
        self.connection = None
        # Инициализируем канал как None
        self.channel = None
        self.retry_count = 0

    def connect(self) -> None:
        """
        Установка соединения с сервером RabbitMQ с повторными попытками.
        """
        while True:
            try:
                connection_params = self.config.get_connection_params()
                self.connection = pika.BlockingConnection(connection_params)
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.config.queue_name)
                logger.info("Successfully connected to RabbitMQ")
                break
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                time.sleep(self.RETRY_DELAY)

    def cleanup(self):
        """Корректное закрытие соединений с RabbitMQ"""
        try:
            if self.channel:
                self.channel.close()
            if self.connection:
                self.connection.close()
            logger.info("Соединения успешно закрыты")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединений: {e}")

    def update_recommendations_async(self, user_id: int, order_id: int, ordered_products: list) -> dict:
        """
        Асинхронное обновление рекомендаций для пользователя
        """
        try:
            # Импортируем необходимые модели и сервисы
            from models.recommendation import Recommendation, ModelType
            from models.orders import Order
            from services.recommendation_service import RecommendationService

            # Создаем сессию БД
            with Session(engine) as session:
                # Проверяем количество заказов пользователя
                user_orders_count = session.exec(
                    select(func.count(Order.id))
                    .where(Order.user_id == user_id)
                ).one()

                if user_orders_count < 2:
                    return {
                        "status": "skipped",
                        "reason": "User has less than 2 orders",
                        "user_id": user_id
                    }

                # Создаем сервис рекомендаций
                recommendation_service = RecommendationService(session)

                # Инвалидируем кеш
                recommendation_service.invalidate_cache(user_id)

                # Если это 2-й или 3-й заказ, переобучаем модель
                if user_orders_count <= 3:
                    logger.info(f"Retraining model for user {user_id} (order #{user_orders_count})")
                    retrain_result = recommendation_service.retrain_model()
                    logger.info(f"Model retrained: {retrain_result}")

                # Генерируем новые рекомендации
                new_recs = recommendation_service.get_recommendations(
                    user_id=user_id,
                    model_type=ModelType.COLLABORATIVE,
                    count=20,
                    use_cache=False
                )

                if new_recs:
                    # Удаляем старые рекомендации
                    deleted = session.query(Recommendation).filter(
                        Recommendation.user_id == user_id,
                        Recommendation.model_type == ModelType.COLLABORATIVE
                    ).delete()

                    # Сохраняем новые рекомендации
                    for rec in new_recs:
                        new_rec = Recommendation(
                            user_id=user_id,
                            product_id=rec["product_id"],
                            score=rec["score"],
                            model_type=ModelType.COLLABORATIVE
                        )
                        session.add(new_rec)

                    session.commit()

                    logger.info(f"Updated {len(new_recs)} recommendations for user {user_id}, deleted {deleted} old")

                    return {
                        "status": "success",
                        "user_id": user_id,
                        "order_id": order_id,
                        "recommendations_updated": len(new_recs),
                        "old_deleted": deleted,
                        "ordered_products": ordered_products,
                        "model_retrained": user_orders_count <= 3
                    }
                else:
                    return {
                        "status": "no_recommendations",
                        "user_id": user_id,
                        "order_id": order_id
                    }

        except Exception as e:
            logger.error(f"Error updating recommendations: {e}")
            return {
                "status": "error",
                "error": str(e),
                "user_id": user_id,
                "order_id": order_id
            }

    def process_message(self, ch, method, properties, body):
        """
        Обработка полученного сообщения из очереди.

        Args:
            ch: Объект канала RabbitMQ
            method: Метод доставки сообщения
            properties: Свойства сообщения
            body: Тело сообщения
        """
        try:
            # Логируем информацию о полученном сообщении
            logger.info(f"Processing message: {body}")

            # Декодируем bytes в строку и затем парсим JSON
            data = json.loads(body.decode('utf-8'))

            # Проверяем тип задачи
            task_type = data.get('task_type')

            if task_type == 'update_recommendations':
                # Реальное обновление рекомендаций
                result = self.update_recommendations_async(
                    data.get('user_id'),
                    data.get('order_id'),
                    data.get('ordered_products', [])
                )
                result_str = json.dumps(result)
            else:
                # Для остальных задач используем старый обработчик
                result_str = do_task(data.get('question', str(data)))

            logger.info(f"Task completed with result: {result_str[:200]}...")

            # Подтверждаем обработку сообщения
            ch.basic_ack(delivery_tag=method.delivery_tag)
            self.retry_count = 0
            logger.info("Message acknowledged")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.retry_count += 1

            if self.retry_count >= self.MAX_RETRIES:
                logger.error("Max retries reached, rejecting message")
                ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
                self.retry_count = 0
            else:
                time.sleep(self.RETRY_DELAY)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start_consuming(self) -> None:
        """
        Запуск процесса получения сообщений из очереди.

        Note:
            Блокирующая операция, прерывается по Ctrl+C
        """
        try:
            # Настраиваем потребление сообщений из очереди
            self.channel.basic_consume(
                queue=self.config.queue_name,  # Имя очереди
                on_message_callback=self.process_message,  # Callback для обработки сообщений
                auto_ack=False  # Отключаем автоматическое подтверждение
            )
            # Логируем информацию о старте потребления сообщений
            logger.info('Started consuming messages. Press Ctrl+C to exit.')
            # Запускаем потребление сообщений
            self.channel.start_consuming()
        except KeyboardInterrupt:
            # Логируем информацию о завершении работы
            logger.info("Shutting down...")
        finally:
            # Закрываем соединение при завершении работы
            self.cleanup()