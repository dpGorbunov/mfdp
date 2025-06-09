# check_db.py
import sys
from pathlib import Path
import psycopg

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from database.config import get_settings


def check_database():
    settings = get_settings()

    conn = psycopg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASS,
        dbname=settings.DB_NAME
    )

    with conn.cursor() as cur:
        print("🔍 Проверка данных в БД:")
        print("=" * 50)

        # Проверяем количество записей в каждой таблице
        tables = [
            ('department', 'Отделы'),
            ('aisle', 'Проходы'),
            ('product', 'Товары'),
            ('users', 'Пользователи'),
            ('orders', 'Заказы'),
            ('orderitem', 'Позиции заказов')
        ]

        for table, name in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"✅ {name}: {count:,}")

        print("\n🔍 Примеры данных из всех таблиц:")
        print("=" * 50)

        # Отделы
        cur.execute('SELECT * FROM department LIMIT 5')
        departments = cur.fetchall()
        print("🏪 ОТДЕЛЫ:")
        for dept in departments:
            print(f"  {dept}")

        # Проходы
        cur.execute('SELECT * FROM aisle LIMIT 5')
        aisles = cur.fetchall()
        print("\n🛒 ПРОХОДЫ:")
        for aisle in aisles:
            print(f"  {aisle}")

        # Товары
        cur.execute('SELECT * FROM product LIMIT 5')
        products = cur.fetchall()
        print("\n🥫 ТОВАРЫ:")
        for product in products:
            print(f"  {product}")

        # Пользователи
        cur.execute('SELECT * FROM users LIMIT 5')
        users = cur.fetchall()
        print("\n👤 ПОЛЬЗОВАТЕЛИ:")
        for user in users:
            print(f"  {user}")

        # Заказы
        cur.execute('SELECT * FROM orders LIMIT 5')
        orders = cur.fetchall()
        print("\n📋 ЗАКАЗЫ:")
        for order in orders:
            print(f"  {order}")

        # Позиции заказов
        cur.execute('SELECT * FROM orderitem LIMIT 5')
        order_items = cur.fetchall()
        print("\n🛍️ ПОЗИЦИИ ЗАКАЗОВ:")
        for item in order_items:
            print(f"  {item}")

        # Проверяем связи
        print("\n🔗 Проверка связей:")
        print("-" * 20)

        # Есть ли заказы без пользователей
        cur.execute('SELECT COUNT(*) FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE u.id IS NULL')
        orphan_orders = cur.fetchone()[0]
        print(f"❌ Заказы без пользователей: {orphan_orders}")

        # Есть ли позиции без заказов
        cur.execute('SELECT COUNT(*) FROM orderitem oi LEFT JOIN orders o ON oi.order_id = o.id WHERE o.id IS NULL')
        orphan_items = cur.fetchone()[0]
        print(f"❌ Позиции без заказов: {orphan_items}")

        # Есть ли товары без отделов/проходов
        cur.execute('SELECT COUNT(*) FROM product p LEFT JOIN aisle a ON p.aisle_id = a.id WHERE a.id IS NULL')
        orphan_products_aisle = cur.fetchone()[0]
        print(f"❌ Товары без проходов: {orphan_products_aisle}")

        cur.execute('SELECT COUNT(*) FROM product p LEFT JOIN department d ON p.department_id = d.id WHERE d.id IS NULL')
        orphan_products_dept = cur.fetchone()[0]
        print(f"❌ Товары без отделов: {orphan_products_dept}")

        # Статистика по активности
        print("\n📊 Статистика:")
        print("-" * 15)

        cur.execute('SELECT AVG(items_count) FROM (SELECT COUNT(*) as items_count FROM orderitem GROUP BY order_id) t')
        avg_items = cur.fetchone()[0]
        print(f"📈 Среднее позиций в заказе: {avg_items:.1f}")

        cur.execute('SELECT COUNT(DISTINCT user_id) FROM orders')
        active_users = cur.fetchone()[0]
        print(f"👥 Пользователей с заказами: {active_users}")

        cur.execute('SELECT MAX(id), MIN(id) FROM users')
        user_range = cur.fetchone()
        print(f"🆔 Диапазон ID пользователей: {user_range[1]} - {user_range[0]}")

        # Дополнительные статистики
        cur.execute('SELECT COUNT(*) FROM orders WHERE user_id <= 100')
        first_100_orders = cur.fetchone()[0]
        print(f"📊 Заказов у первых 100 пользователей: {first_100_orders}")

        cur.execute('SELECT d.name, COUNT(p.id) FROM department d LEFT JOIN product p ON d.id = p.department_id GROUP BY d.name ORDER BY COUNT(p.id) DESC LIMIT 5')
        top_depts = cur.fetchall()
        print(f"\n🏪 Топ-5 отделов по количеству товаров:")
        for dept in top_depts:
            print(f"  {dept[0]}: {dept[1]} товаров")

        cur.execute('SELECT p.name, COUNT(oi.id) as order_count FROM product p JOIN orderitem oi ON p.id = oi.product_id GROUP BY p.id, p.name ORDER BY order_count DESC LIMIT 5')
        popular_products = cur.fetchall()
        print(f"\n🔥 Топ-5 популярных товаров:")
        for product in popular_products:
            print(f"  {product[0]}: заказано {product[1]} раз")

        cur.execute('SELECT u.id, u.name, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id, u.name ORDER BY order_count DESC LIMIT 5')
        active_users = cur.fetchall()
        print(f"\n👑 Топ-5 активных пользователей:")
        for user in active_users:
            print(f"  {user[1]} (ID: {user[0]}): {user[2]} заказов")

    conn.close()
    print("\n✅ Проверка завершена!")


if __name__ == "__main__":
    check_database()
