"""Exporta todos os modelos para que o Alembic e o restante da aplicação
enxerguem o metadata completo com um único import."""
from app.models.base import TenantMixin, TimestampMixin
from app.models.tenant import Tenant
from app.models.user import User
from app.models.ingredient import Ingredient, MeasureUnit
from app.models.ingredient_lot import IngredientLot
from app.models.product import Product
from app.models.product_recipe import ProductRecipe
from app.models.stock_movement import MovementType, StockMovement
from app.models.order import Order, OrderItem, OrderSource, OrderStatus

__all__ = [
    "TenantMixin",
    "TimestampMixin",
    "Tenant",
    "User",
    "Ingredient",
    "IngredientLot",
    "MeasureUnit",
    "Product",
    "ProductRecipe",
    "MovementType",
    "StockMovement",
    "Order",
    "OrderItem",
    "OrderSource",
    "OrderStatus",
]
