import logging
import json
from typing import Optional
import random

# Настраиваем общий уровень логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


def do_task(text: str) -> str:
    """
    Заглушка для обработки ML задач.
    В реальном проекте здесь будет вызов ML модели.

    Args:
        text: Входящий текст для обработки

    Returns:
        str: Результат обработки
    """
    try:
        # Заглушка для демонстрации работы
        # В реальном проекте здесь будет обработка ML моделью

        # Простая имитация обработки
        if "рекомендация" in text.lower() or "recommendation" in text.lower():
            responses = [
                "Рекомендуем товары из категории 'Популярное'",
                "На основе ваших предпочтений предлагаем товары из отдела 'Молочные продукты'",
                "Персональная рекомендация: попробуйте товары из раздела 'Свежие овощи'"
            ]
            return random.choice(responses)

        elif "анализ" in text.lower() or "analysis" in text.lower():
            return "Анализ завершен: найдены популярные товары в вашем регионе"

        else:
            # Простое эхо с префиксом
            return f"ML обработано: {text[:50]}..."

    except Exception as e:
        logger.error(f"Error in do_task: {e}")
        return 'Ошибка при обработке запроса'