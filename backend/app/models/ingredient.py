"""Ingrediente / matéria-prima. O estoque é derivado dos lotes (IngredientLot)."""
import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin, uuid_pk


class MeasureUnit(str, enum.Enum):
    """Unidades de medida suportadas para estoque."""

    KG = "kg"
    G = "g"
    L = "l"
    ML = "ml"
    UN = "un"  # unidade (ex: embalagem, lata)


class Ingredient(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ingredients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_ingredients_tenant_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[MeasureUnit] = mapped_column(
        Enum(MeasureUnit, name="measure_unit", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )

    # Abaixo deste valor o ingrediente entra no alerta de "estoque crítico"
    min_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal("0"), nullable=False
    )
    # Custo de referência por unidade (o custo real vive em cada lote)
    cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    # Lotes do ingrediente, na ordem de consumo FEFO (validade mais próxima
    # primeiro; sem validade por último). selectin: carrega junto sem N+1,
    # necessário para a propriedade total_quantity funcionar em contexto async.
    lots: Mapped[list["IngredientLot"]] = relationship(  # noqa: F821
        back_populates="ingredient",
        lazy="selectin",
        order_by="IngredientLot.expiration_date.asc().nulls_last(), IngredientLot.created_at.asc()",
        cascade="all, delete-orphan",
    )

    @property
    def total_quantity(self) -> Decimal:
        """Estoque total = soma dos saldos de todos os lotes ativos."""
        return sum(
            (lot.current_quantity for lot in self.lots if lot.current_quantity > 0),
            Decimal("0"),
        )

    @property
    def weighted_average_cost(self) -> Decimal | None:
        """Custo médio ponderado pelos saldos dos lotes ativos (None sem estoque)."""
        total = self.total_quantity
        if total == 0:
            return None
        value = sum(
            (lot.current_quantity * lot.unit_cost for lot in self.lots if lot.current_quantity > 0),
            Decimal("0"),
        )
        return (value / total).quantize(Decimal("0.0001"))
