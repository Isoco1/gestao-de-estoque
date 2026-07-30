"""Ficha técnica (BOM): quanto de cada ingrediente compõe 1 unidade do produto.

Exemplo: 1 Pizza Calabresa = 300 (g) de Massa + 150 (g) de Queijo.
A quantidade é expressa na unidade de medida do próprio ingrediente.
"""
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, uuid_pk
from app.models.ingredient import Ingredient


class ProductRecipe(Base, TenantMixin, TimestampMixin):
    __tablename__ = "product_recipes"
    __table_args__ = (
        # Um ingrediente aparece no máximo uma vez por produto
        UniqueConstraint("product_id", "ingredient_id", name="uq_recipe_product_ingredient"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Quantidade do ingrediente (na unidade dele) para 1 unidade do produto
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="recipe_items")  # noqa: F821
    ingredient: Mapped[Ingredient] = relationship(lazy="joined")
