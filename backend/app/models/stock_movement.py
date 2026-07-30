"""Histórico imutável de movimentações de estoque (entradas, baixas, perdas)."""
import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, uuid_pk
from app.models.ingredient import Ingredient


class MovementType(str, enum.Enum):
    ENTRY = "entrada"            # compra / reposição
    SALE_WHATSAPP = "venda_whatsapp"  # baixa automática via webhook Z-API
    SALE_MANUAL = "venda_manual"      # venda lançada no painel
    LOSS = "perda"               # quebra, validade vencida, desperdício
    ADJUSTMENT = "ajuste"        # correção de inventário


class StockMovement(Base, TenantMixin, TimestampMixin):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = uuid_pk()
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    # Quantidade com sinal: positiva em entradas, negativa em baixas/perdas
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    # Saldo do ingrediente APÓS a movimentação (facilita auditoria)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Origem legível do lançamento (ex: "Venda WhatsApp")
    origin: Mapped[str | None] = mapped_column(String(120))
    # Venda que originou a baixa, quando aplicável
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    # Lote afetado pela movimentação (rastreabilidade FEFO)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingredient_lots.id", ondelete="SET NULL"), index=True
    )

    ingredient: Mapped[Ingredient] = relationship(lazy="joined")
