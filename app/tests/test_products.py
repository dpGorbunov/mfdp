from fastapi.testclient import TestClient


def test_get_products(client: TestClient):
    """Тест получения списка продуктов"""
    response = client.get("/products/")
    assert response.status_code == 200

    products = response.json()
    assert isinstance(products, list)
    assert len(products) >= 2


def test_get_product_by_id(client: TestClient):
    """Тест получения продукта по ID"""
    response = client.get("/products/1")
    assert response.status_code == 200

    product = response.json()
    assert product["id"] == 1
    assert product["name"] == "Organic Banana"


def test_get_nonexistent_product(client: TestClient):
    """Тест получения несуществующего продукта"""
    response = client.get("/products/9999")
    assert response.status_code == 404


def test_search_products(client: TestClient):
    """Тест поиска продуктов"""
    response = client.get("/products/?search=banana")
    assert response.status_code == 200

    products = response.json()
    assert len(products) > 0
    assert any("banana" in p["name"].lower() for p in products)


def test_filter_by_department(client: TestClient):
    """Тест фильтрации по отделу"""
    response = client.get("/products/?department_id=1")
    assert response.status_code == 200

    products = response.json()
    assert all(p["department_id"] == 1 for p in products)


def test_get_departments(client: TestClient):
    """Тест получения списка отделов"""
    response = client.get("/products/departments/list")
    assert response.status_code == 200

    departments = response.json()
    assert len(departments) >= 2
    assert any(d["name"] == "Produce" for d in departments)