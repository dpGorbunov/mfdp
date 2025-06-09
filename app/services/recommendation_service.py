# app/services/recommendation_service.py
import pandas as pd
import numpy as np
from scipy.sparse import coo_matrix
from sklearn.metrics.pairwise import cosine_similarity
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from typing import List, Dict, Tuple, Optional
import logging
import time
import json
from datetime import datetime, timedelta
from numpy import bincount, log, sqrt

from models.product import Product
from models.orders import Order
from models.order_item import OrderItem
from models.recommendation import ModelType, Recommendation
from database.database import redis_client

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, session: Session):
        self.session = session
        self.user_product_matrix = None
        self.tf_idf_matrix = None
        self.df_user_products = None
        self.df_product_frequency = None
        self.user_id_map = {}
        self.product_id_map = {}
        self.reverse_user_map = {}
        self.reverse_product_map = {}
        self.popular_products = []
        self._product_cache = {}
        self._is_trained = False
        self.redis = redis_client if redis_client else None
        self._popular_cache_key = "popular_products_cache"
        self._popular_cache_ttl = 3600  # 1 час

    def load_data(self) -> Dict:
        """Загрузка и подготовка данных из БД с кэшированием"""
        logger.info("Загрузка данных из БД...")

        # Загружаем все продукты в кэш одним запросом
        products = self.session.exec(
            select(Product)
            .options(
                selectinload(Product.aisle),
                selectinload(Product.department)
            )
        ).all()

        self._product_cache = {p.id: p for p in products}
        logger.info(f"Загружено {len(self._product_cache)} продуктов в кэш")

        # Получаем данные заказов
        query = select(
            OrderItem.order_id,
            OrderItem.product_id,
            OrderItem.quantity,
            Order.user_id
        ).select_from(OrderItem).join(Order, OrderItem.order_id == Order.id)

        results = self.session.exec(query).all()

        if not results:
            raise ValueError("Нет данных для обучения")

        # Создаем DataFrame
        df_data = pd.DataFrame([
            {
                "order_id": r.order_id,
                "product_id": r.product_id,
                "quantity": r.quantity,
                "user_id": r.user_id
            }
            for r in results
        ])

        # Группируем по пользователям и продуктам
        df_user_product = (
            df_data.groupby(["user_id", "product_id"])
            .agg({"quantity": "sum"})
            .reset_index()
        )

        # Создаем df_user_products
        self.df_user_products = (
            df_user_product.groupby("user_id")["product_id"]
            .apply(list)
            .reset_index()
        )

        # Частота продуктов
        product_counts = df_user_product.groupby("product_id")["quantity"].sum()
        self.df_product_frequency = pd.DataFrame({
            "product_id": product_counts.index,
            "frequency": product_counts.values
        }).set_index("product_id")

        # Популярные продукты
        self.popular_products = (
            self.df_product_frequency
            .nlargest(100, "frequency")
            .index.tolist()
        )

        # Создаем маппинги
        unique_users = df_user_product["user_id"].unique()
        unique_products = df_user_product["product_id"].unique()

        self.user_id_map = {idx: user_id for idx, user_id in enumerate(unique_users)}
        self.product_id_map = {idx: product_id for idx, product_id in enumerate(unique_products)}

        # Обратные маппинги
        self.reverse_user_map = {user_id: idx for idx, user_id in self.user_id_map.items()}
        self.reverse_product_map = {product_id: idx for idx, product_id in self.product_id_map.items()}

        # Создаем индексы для матрицы
        user_indices = df_user_product["user_id"].map(self.reverse_user_map)
        product_indices = df_user_product["product_id"].map(self.reverse_product_map)

        # Построение user-product матрицы
        self.user_product_matrix = coo_matrix(
            (df_user_product["quantity"], (user_indices, product_indices)),
            shape=(len(unique_users), len(unique_products))
        ).tocsr()

        # Рассчитываем разреженность
        total_size = self.user_product_matrix.shape[0] * self.user_product_matrix.shape[1]
        actual_size = self.user_product_matrix.nnz
        sparsity = (1 - (actual_size / total_size)) * 100

        stats = {
            "users": len(self.user_id_map),
            "products": len(self.product_id_map),
            "interactions": actual_size,
            "sparsity": sparsity
        }

        logger.info(f"Данные загружены: {stats}")

        # Обновляем кеш популярных товаров
        self._update_popular_cache()

        return stats

    def _update_popular_cache(self):
        """Обновляет кеш популярных товаров"""
        try:
            # Получаем топ-50 популярных товаров с деталями
            popular_details = self._get_product_details(self.popular_products[:50], [0.5] * 50)

            if self.redis:
                # Сохраняем в Redis
                self.redis.setex(
                    self._popular_cache_key,
                    self._popular_cache_ttl,
                    json.dumps(popular_details)
                )
                logger.info(f"Популярные товары сохранены в Redis кеш")
            else:
                # Сохраняем в таблицу рекомендаций если Redis недоступен
                self._save_popular_to_db(popular_details)

        except Exception as e:
            logger.error(f"Ошибка при обновлении кеша популярных товаров: {e}")

    def _save_popular_to_db(self, popular_products: List[Dict]):
        """Сохраняет популярные товары в таблицу рекомендаций"""
        try:
            # Удаляем старые популярные рекомендации
            self.session.query(Recommendation).filter(
                Recommendation.user_id == 0,  # Используем user_id=0 для общих рекомендаций
                Recommendation.model_type == ModelType.POPULAR
            ).delete()

            # Добавляем новые
            for idx, product in enumerate(popular_products):
                rec = Recommendation(
                    user_id=0,
                    product_id=product["product_id"],
                    score=product["score"],
                    model_type=ModelType.POPULAR
                )
                self.session.add(rec)

            self.session.commit()
            logger.info(f"Сохранено {len(popular_products)} популярных товаров в БД")

        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка при сохранении популярных товаров в БД: {e}")

    def _get_popular_from_cache(self, count: int = 10) -> Optional[List[Dict]]:
        """Получает популярные товары из кеша"""
        try:
            if self.redis:
                cached = self.redis.get(self._popular_cache_key)
                if cached:
                    popular = json.loads(cached)
                    logger.info(f"Загружены популярные товары из Redis кеша")
                    return popular[:count]
            else:
                # Пробуем загрузить из БД
                recs = self.session.exec(
                    select(Recommendation)
                    .where(
                        Recommendation.user_id == 0,
                        Recommendation.model_type == ModelType.POPULAR
                    )
                    .order_by(Recommendation.score.desc())
                    .limit(count)
                ).all()

                if recs:
                    logger.info(f"Загружены популярные товары из БД")
                    return [
                        {
                            "product_id": rec.product_id,
                            "product_name": self._product_cache.get(rec.product_id,
                                                                    {}).name if rec.product_id in self._product_cache else f"Product {rec.product_id}",
                            "score": rec.score,
                            "aisle_name": self._product_cache.get(rec.product_id,
                                                                  {}).aisle.name if rec.product_id in self._product_cache and
                                                                                    self._product_cache[
                                                                                        rec.product_id].aisle else None,
                            "department_name": self._product_cache.get(rec.product_id,
                                                                       {}).department.name if rec.product_id in self._product_cache and
                                                                                              self._product_cache[
                                                                                                  rec.product_id].department else None
                        }
                        for rec in recs
                    ]

        except Exception as e:
            logger.error(f"Ошибка при загрузке популярных товаров из кеша: {e}")

        return None

    def save_recommendations_to_db(self, user_id: int, recommendations: List[Dict], model_type: ModelType):
        """Сохраняет рекомендации в БД"""
        try:
            logger.info(
                f"Saving recommendations to DB: user_id={user_id}, count={len(recommendations)}, model_type={model_type}")

            # Удаляем старые рекомендации пользователя для данного типа модели
            deleted_count = self.session.query(Recommendation).filter(
                Recommendation.user_id == user_id,
                Recommendation.model_type == model_type
            ).count()

            self.session.query(Recommendation).filter(
                Recommendation.user_id == user_id,
                Recommendation.model_type == model_type
            ).delete()

            logger.info(f"Deleted {deleted_count} old recommendations")

            # Добавляем новые рекомендации
            for rec in recommendations:
                recommendation = Recommendation(
                    user_id=user_id,
                    product_id=rec["product_id"],
                    score=rec["score"],
                    model_type=model_type.value if hasattr(model_type, 'value') else str(model_type)
                )
                self.session.add(recommendation)

            self.session.commit()
            logger.info(f"Successfully saved {len(recommendations)} recommendations for user {user_id}")

        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка при сохранении рекомендаций: {e}")
            raise

    def tfidf_weight(self, tf_matrix):
        """TF-IDF взвешивание"""
        tf_idf = coo_matrix(tf_matrix)
        N = float(tf_idf.shape[0])
        idf = log(N / (1 + bincount(tf_idf.col)))
        tf_idf.data = sqrt(tf_idf.data) * idf[tf_idf.col]
        return tf_idf.tocsr()

    def train_model(self) -> Dict:
        """Обучение TF-IDF модели"""
        logger.info("Обучение TF-IDF модели...")
        start_time = time.time()

        if self.user_product_matrix is None:
            stats = self.load_data()
        else:
            stats = {"loaded": "from_cache"}

        # Применяем TF-IDF
        self.tf_idf_matrix = self.tfidf_weight(self.user_product_matrix)
        self._is_trained = True

        training_time = time.time() - start_time
        logger.info(f"Модель обучена за {training_time:.2f}s")

        stats.update({
            "training_time": training_time,
            "model_shape": self.tf_idf_matrix.shape,
            "status": "trained"
        })
        return stats

    def generate_recommendations_tfidf(
            self,
            target_user_id: int,
            k_neighbors: int = 30,
            n_recommendations: int = 10
    ) -> Tuple[List[int], List[float]]:
        """Генерация рекомендаций TF-IDF"""

        if not self._is_trained:
            self.train_model()

        # Проверяем есть ли пользователь
        if target_user_id not in self.reverse_user_map:
            logger.info(f"Новый пользователь {target_user_id}, возвращаем популярные")
            return self.popular_products[:n_recommendations], [0.5] * min(n_recommendations, len(self.popular_products))

        user_idx = self.reverse_user_map[target_user_id]

        # Получаем вектор пользователя
        target_user_vector = self.tf_idf_matrix[user_idx]

        # Проверяем, что у пользователя есть покупки
        if target_user_vector.nnz == 0:
            logger.warning(f"Пользователь {target_user_id} не имеет покупок в матрице")
            return self.popular_products[:n_recommendations], [0.5] * min(n_recommendations, len(self.popular_products))

        # Вычисляем косинусное сходство
        similarities = cosine_similarity(
            self.tf_idf_matrix,
            target_user_vector.reshape(1, -1),
            dense_output=False
        )
        cos_vec = similarities.toarray().flatten()

        # Получаем продукты пользователя
        user_products_row = self.df_user_products[self.df_user_products['user_id'] == target_user_id]
        if not user_products_row.empty:
            user_products = set(user_products_row.iloc[0]['product_id'])
        else:
            user_products = set()

        logger.info(f"Пользователь {target_user_id} купил {len(user_products)} уникальных товаров")

        # Исключаем самого пользователя
        cos_vec[user_idx] = -1

        # Находим топ-K похожих пользователей
        k_to_check = min(k_neighbors * 2, len(cos_vec) - 1)
        top_k_indices = np.argpartition(cos_vec, -k_to_check)[-k_to_check:]
        top_k_indices = top_k_indices[np.argsort(cos_vec[top_k_indices])[::-1]]

        # Собираем рекомендации с весами
        recommendation_scores = {}
        similar_users_found = 0

        for similar_user_idx in top_k_indices:
            if cos_vec[similar_user_idx] <= 0:
                continue

            similar_user_id = self.user_id_map[similar_user_idx]
            similar_user_row = self.df_user_products[self.df_user_products['user_id'] == similar_user_id]

            if similar_user_row.empty:
                continue

            similar_products = set(similar_user_row.iloc[0]['product_id'])

            candidate_products = similar_products

            if not candidate_products:
                continue

            similar_users_found += 1
            similarity_score = cos_vec[similar_user_idx]

            # Добавляем продукты с учетом схожести
            for product in candidate_products:
                if product not in recommendation_scores:
                    recommendation_scores[product] = []
                recommendation_scores[product].append(similarity_score)

                # Бонус для уже купленных товаров (опционально)
                if product in user_products:
                    recommendation_scores[product].append(similarity_score * 0.3)  # Дополнительный вес

            if similar_users_found >= k_neighbors:
                break

        logger.info(f"Найдено {similar_users_found} похожих пользователей с {len(recommendation_scores)} кандидатами")

        if not recommendation_scores:
            logger.warning(f"Не найдено рекомендаций для пользователя {target_user_id}, возвращаем популярные")
            # Fallback к популярным (тоже не фильтруем)
            return self.popular_products[:n_recommendations], [0.3] * min(n_recommendations, len(self.popular_products))

        # Ранжируем кандидатов
        scored_recommendations = []
        for product, scores in recommendation_scores.items():
            # Средняя схожесть
            avg_similarity = np.mean(scores)

            # Учитываем популярность
            if product in self.df_product_frequency.index:
                freq = self.df_product_frequency.loc[product, 'frequency']
                max_freq = self.df_product_frequency['frequency'].max()
                popularity_score = freq / max_freq

                # Комбинированный score
                final_score = 0.7 * avg_similarity + 0.3 * popularity_score
            else:
                final_score = avg_similarity

            scored_recommendations.append((final_score, product))

        # Сортируем и берем топ-N
        scored_recommendations.sort(reverse=True, key=lambda x: x[0])
        top_recommendations = scored_recommendations[:n_recommendations]

        # Возвращаем продукты и scores
        recommended_products = [item[1] for item in top_recommendations]
        scores = [min(item[0], 1.0) for item in top_recommendations]

        logger.info(f"Возвращаем {len(recommended_products)} рекомендаций для пользователя {target_user_id}")

        return recommended_products, scores

    def get_recommendations(
            self,
            user_id: int,
            model_type: ModelType = ModelType.COLLABORATIVE,
            count: int = 10,
            use_cache: bool = True,
            exclude_products: List[int] = None
    ) -> List[Dict]:
        """Основной метод получения рекомендаций"""

        logger.info(
            f"RecommendationService.get_recommendations called: user_id={user_id}, model_type={model_type}, count={count}, use_cache={use_cache}")

        if model_type == ModelType.POPULAR:
            # Сначала пробуем загрузить из кеша
            if use_cache:
                cached_popular = self._get_popular_from_cache(count * 2)  # Берем больше для фильтрации
                if cached_popular:
                    # Фильтруем исключенные товары
                    if exclude_products:
                        filtered = [p for p in cached_popular if p["product_id"] not in exclude_products]
                        return filtered[:count]
                    return cached_popular[:count]

            # Если кеша нет, загружаем данные и генерируем
            if not self.popular_products:
                try:
                    self.load_data()
                except Exception as e:
                    logger.error(f"Ошибка при загрузке данных: {e}")
                    # Возвращаем пустой список или дефолтные товары
                    return []

            # Фильтруем исключенные товары
            if exclude_products:
                product_ids = [pid for pid in self.popular_products if pid not in exclude_products][:count]
            else:
                product_ids = self.popular_products[:count]

            scores = [0.5] * len(product_ids)

        elif model_type == ModelType.COLLABORATIVE:
            # Получаем больше рекомендаций для фильтрации
            product_ids, scores = self.generate_recommendations_tfidf(user_id, n_recommendations=count * 2)

            logger.info(f"Generated {len(product_ids)} recommendations for user {user_id}")

            # Фильтруем исключенные товары
            if exclude_products:
                filtered_pairs = [(pid, score) for pid, score in zip(product_ids, scores)
                                  if pid not in exclude_products]
                product_ids = [p[0] for p in filtered_pairs][:count]
                scores = [p[1] for p in filtered_pairs][:count]
            else:
                product_ids = product_ids[:count]
                scores = scores[:count]

            # Получаем детали продуктов
            recommendations = self._get_product_details(product_ids, scores)

            logger.info(f"Got {len(recommendations)} product details, use_cache={use_cache}")

            # Сохраняем в БД для последующего использования
            if recommendations and not use_cache:  # Сохраняем только при явной генерации
                logger.info(f"Saving {len(recommendations)} recommendations to DB for user {user_id}")
                self.save_recommendations_to_db(user_id, recommendations, model_type)

            return recommendations
        else:
            raise ValueError(f"Неподдерживаемый тип модели: {model_type}")

        # Получаем информацию о продуктах
        return self._get_product_details(product_ids, scores)

    def _get_product_details(self, product_ids: List[int], scores: List[float]) -> List[Dict]:
        """Оптимизированное получение деталей продуктов"""
        recommendations = []

        # Если есть кэш - используем его
        if self._product_cache:
            for product_id, score in zip(product_ids, scores):
                if product_id in self._product_cache:
                    product = self._product_cache[product_id]
                    recommendations.append({
                        "product_id": product.id,
                        "product_name": product.name,
                        "score": round(float(score), 3),
                        "aisle_name": product.aisle.name if product.aisle else None,
                        "department_name": product.department.name if product.department else None
                    })
        else:
            # Загружаем продукты одним запросом
            if product_ids:
                products = self.session.exec(
                    select(Product)
                    .options(
                        selectinload(Product.aisle),
                        selectinload(Product.department)
                    )
                    .where(Product.id.in_(product_ids))
                ).all()

                product_dict = {p.id: p for p in products}

                for product_id, score in zip(product_ids, scores):
                    if product_id in product_dict:
                        product = product_dict[product_id]
                        recommendations.append({
                            "product_id": product.id,
                            "product_name": product.name,
                            "score": round(float(score), 3),
                            "aisle_name": product.aisle.name if product.aisle else None,
                            "department_name": product.department.name if product.department else None
                        })

        return recommendations

    def retrain_model(self) -> Dict:
        """Переобучение модели"""
        try:
            # Сбрасываем кэши
            self._product_cache.clear()
            self._is_trained = False

            # Очищаем кеш популярных товаров
            if self.redis:
                self.redis.delete(self._popular_cache_key)

            return self.train_model()
        except Exception as e:
            logger.error(f"Ошибка переобучения: {e}")
            return {"status": "error", "error": str(e)}

    def invalidate_cache(self, user_id: int):
        """Инвалидация кеша для пользователя"""
        # В текущей реализации кеш пользователей не используется
        # Но можно добавить инвалидацию популярных товаров при необходимости
        pass