# app/routes/__init__.py
from .auth import router as auth
from .products import router as products
from .recommendations import router as recommendations
from .orders import router as orders

__all__ = ["auth", "products", "recommendations", "orders"]