"""Venda (Order) e seus itens (OrderItem)."""
import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, uuid_pk
from app.models.product import Product


class OrderSource(str, enum.Enum):
    WHATSAPP = "whatsapp"
    MANUAL = "manual"


class OrderStatus(str, enum.Enum):
    PROCESSED = "processado"   # estoque baixado com sucesso
    FAILED = "falhou"          # ex: estoque insuficiente -> transação revertida


class Order(Base, TenantMixin, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = uuid_pk()
    source: Mapped[OrderSource] = mapped_column(
        Enum(OrderSource, name="order_source", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    customer_phone: Mapped[str | None] = mapped_column(String(20))
    # Mensagem original recebida do WhatsApp (rastreabilidade)
    raw_message: Mapped[str | None] = mapped_column(Text)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base, TenantMixin, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(lazy="joined")
