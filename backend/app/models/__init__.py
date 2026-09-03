"""Exporta todos os modelos para que o Alembic e o restante da aplicação
enxerguem o metadata completo com um único import."""
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.models.ingredient import Ingredient, MeasureUnit
from app.models.ingredient_lot import IngredientLot
from app.models.product import Product
from app.models.product_recipe import ProductRecipe
from app.models.stock_movement import MovementType, StockMovement
from app.models.order import Order, OrderItem, OrderSource, OrderStatus
from app.models.audit_log import AuditLog

__all__ = [
    "SoftDeleteMixin",
    "TenantMixin",
    "TimestampMixin",
    "Tenant",
    "TenantStatus",
    "User",
    "UserRole",
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
    "AuditLog",
]
