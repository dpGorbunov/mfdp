#!/usr/bin/env python3
# transfer_recs.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session
from app.database.database import engine
from app.models.recommendation import Recommendation


def transfer_recommendations(from_user_id, to_user_id):
    with Session(engine) as session:
        # Получаем рекомендации
        recs = session.query(Recommendation).filter(
            Recommendation.user_id == from_user_id,
            Recommendation.model_type == 'collaborative'
        ).all()

        print(f"Найдено {len(recs)} рекомендаций для переноса")

        # Удаляем старые рекомендации целевого пользователя
        deleted = session.query(Recommendation).filter(
            Recommendation.user_id == to_user_id,
            Recommendation.model_type == 'collaborative'
        ).delete()

        print(f"Удалено {deleted} старых рекомендаций")

        # Переносим
        for rec in recs:
            new_rec = Recommendation(
                user_id=to_user_id,
                product_id=rec.product_id,
                score=rec.score,
                model_type=rec.model_type
            )
            session.add(new_rec)

        session.commit()
        print(f"Перенесено {len(recs)} рекомендаций от user {from_user_id} к user {to_user_id}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python transfer_recs.py FROM_USER_ID TO_USER_ID")
        print("Example: python transfer_recs.py 1005 1")
        sys.exit(1)

    transfer_recommendations(int(sys.argv[1]), int(sys.argv[2]))