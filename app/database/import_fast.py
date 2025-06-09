# app/database/import_fast.py
import sys
import pandas as pd
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, text, SQLModel
import psycopg
from database.config import get_settings
from database.database import engine
from auth.hash_password import HashPassword


def import_fast(data_dir="data", max_users=None, recreate=True):
    data_dir = Path(data_dir)
    settings = get_settings()

    # Прямое подключение к PostgreSQL
    conn = psycopg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASS,
        dbname=settings.DB_NAME
    )

    with conn.cursor() as cur:
        if recreate:
            print("🗑️ Удаление всех таблиц...")
            cur.execute("DROP TABLE IF EXISTS recommendation CASCADE")
            cur.execute("DROP TABLE IF EXISTS orderitem CASCADE")
            cur.execute("DROP TABLE IF EXISTS orders CASCADE")
            cur.execute("DROP TABLE IF EXISTS users CASCADE")
            cur.execute("DROP TABLE IF EXISTS product CASCADE")
            cur.execute("DROP TABLE IF EXISTS aisle CASCADE")
            cur.execute("DROP TABLE IF EXISTS department CASCADE")

            print("🏗️ Создание новых таблиц...")
            # Создаём таблицы вручную
            cur.execute("""
                CREATE TABLE department (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE aisle (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE product (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    aisle_id INTEGER REFERENCES aisle(id),
                    department_id INTEGER REFERENCES department(id),
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)

            cur.execute("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255),
                    name VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE orderitem (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(id),
                    product_id INTEGER REFERENCES product(id),
                    quantity INTEGER DEFAULT 1
                )
            """)

            # Создаем таблицу рекомендаций
            cur.execute("""
                CREATE TABLE recommendation (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    product_id INTEGER NOT NULL REFERENCES product(id),
                    score FLOAT NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
                    model_type VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, product_id, model_type)
                )
            """)

            # Создаем индексы для оптимизации
            cur.execute("CREATE INDEX idx_recommendation_user_id ON recommendation(user_id)")
            cur.execute("CREATE INDEX idx_recommendation_model_type ON recommendation(model_type)")
            cur.execute("CREATE INDEX idx_recommendation_score ON recommendation(score DESC)")

            conn.commit()
        else:
            # Очистка только при не-пересоздании
            cur.execute(
                'TRUNCATE TABLE recommendation, orderitem, orders, users, product, aisle, department RESTART IDENTITY CASCADE')
            conn.commit()
            print("✅ БД очищена")

        # Отделы
        df = pd.read_csv(data_dir / "departments.csv")
        for _, row in df.iterrows():
            cur.execute("INSERT INTO department (id, name) VALUES (%s, %s)",
                        (int(row['department_id']), row['department']))
        conn.commit()
        print(f"✅ Отделы: {len(df)}")

        # Проходы
        df = pd.read_csv(data_dir / "aisles.csv")
        for _, row in df.iterrows():
            cur.execute("INSERT INTO aisle (id, name) VALUES (%s, %s)",
                        (int(row['aisle_id']), row['aisle']))
        conn.commit()
        print(f"✅ Проходы: {len(df)}")

        # Товары
        df = pd.read_csv(data_dir / "products.csv")
        cur.executemany(
            "INSERT INTO product (id, name, aisle_id, department_id, is_active) VALUES (%s, %s, %s, %s, %s)",
            [(int(row['product_id']), row['product_name'], int(row['aisle_id']), int(row['department_id']), True)
             for _, row in df.iterrows()])
        conn.commit()
        print(f"✅ Товары: {len(df)}")

        # Заказы
        df_orders = pd.read_csv(data_dir / "orders.csv")
        if max_users:
            users = df_orders['user_id'].unique()[:max_users]
            df_orders = df_orders[df_orders['user_id'].isin(users)]

        # Пользователи
        hash_pwd = HashPassword().create_hash("instacart123")
        unique_users = df_orders['user_id'].unique()

        # Добавляем специального пользователя с ID=0 для популярных товаров
        cur.execute(
            "INSERT INTO users (id, email, password_hash, name, is_active, created_at) VALUES (%s, %s, %s, %s, %s, NOW()) ON CONFLICT (id) DO NOTHING",
            (0, "system@internal.com", hash_pwd, "System", True)
        )

        cur.executemany(
            "INSERT INTO users (id, email, password_hash, name, is_active, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
            [(int(uid), f"user{uid}@test.com", hash_pwd, f"User {uid}", True) for uid in unique_users])
        conn.commit()
        print(f"✅ Пользователи: {len(unique_users) + 1}")

        # Заказы
        cur.executemany("INSERT INTO orders (id, user_id, created_at) VALUES (%s, %s, NOW())",
                        [(int(row['order_id']), int(row['user_id'])) for _, row in df_orders.iterrows()])
        conn.commit()
        print(f"✅ Заказы: {len(df_orders)}")

        # Позиции заказов
        valid_orders = set(df_orders['order_id'])
        total = 0

        for chunk in pd.read_csv(data_dir / "order_products__prior.csv", chunksize=50000):
            chunk = chunk[chunk['order_id'].isin(valid_orders)]
            if len(chunk) > 0:
                cur.executemany("INSERT INTO orderitem (order_id, product_id, quantity) VALUES (%s, %s, %s)",
                                [(int(row['order_id']), int(row['product_id']), 1) for _, row in chunk.iterrows()])
                conn.commit()
                total += len(chunk)

        print(f"✅ Позиции: {total}")

        # Исправляем последовательности для всех таблиц с SERIAL
        print("🔧 Настройка последовательностей...")

        # Для users
        cur.execute("""
            SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 0) + 1, false);
        """)

        # Для других таблиц тоже на всякий случай
        cur.execute("""
            SELECT setval('department_id_seq', COALESCE((SELECT MAX(id) FROM department), 0) + 1, false);
        """)

        cur.execute("""
            SELECT setval('aisle_id_seq', COALESCE((SELECT MAX(id) FROM aisle), 0) + 1, false);
        """)

        cur.execute("""
            SELECT setval('product_id_seq', COALESCE((SELECT MAX(id) FROM product), 0) + 1, false);
        """)

        cur.execute("""
            SELECT setval('orders_id_seq', COALESCE((SELECT MAX(id) FROM orders), 0) + 1, false);
        """)

        cur.execute("""
            SELECT setval('orderitem_id_seq', COALESCE((SELECT MAX(id) FROM orderitem), 0) + 1, false);
        """)

        cur.execute("""
            SELECT setval('recommendation_id_seq', COALESCE((SELECT MAX(id) FROM recommendation), 0) + 1, false);
        """)

        conn.commit()
        print("✅ Последовательности настроены")

    conn.close()


if __name__ == "__main__":
    recreate_db = "--no-recreate" not in sys.argv  # По умолчанию пересоздаём

    if "--no-recreate" in sys.argv:
        sys.argv.remove("--no-recreate")

    max_users = int(sys.argv[1]) if len(sys.argv) > 1 else None

    if recreate_db:
        print("🔄 Режим: полное пересоздание БД")
    else:
        print("📊 Режим: только загрузка данных")

    import_fast(max_users=max_users, recreate=recreate_db)