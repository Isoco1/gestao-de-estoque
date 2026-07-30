"""Produto vendido ao cliente final (ex: Pizza Calabresa)."""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, uuid_pk


class Product(Base, TenantMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_products_tenant_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Ficha técnica (itens da receita). selectin evita N+1 em listagens.
    recipe_items: Mapped[list["ProductRecipe"]] = relationship(  # noqa: F821
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
