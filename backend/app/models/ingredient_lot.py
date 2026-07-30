"""Lote de ingrediente: cada entrada de mercadoria vira um lote com
validade, fornecedor e custo próprios.

O estoque total do ingrediente é a SOMA dos lotes com saldo — o campo
estático de estoque deixou de existir. A baixa segue FEFO (First Expired,
First Out): consome primeiro o lote com validade mais próxima.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, uuid_pk


class IngredientLot(Base, TenantMixin, TimestampMixin):
    __tablename__ = "ingredient_lots"

    id: Mapped[uuid.UUID] = uuid_pk()
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Código do lote informado pelo fabricante/fornecedor (opcional)
    batch_number: Mapped[str | None] = mapped_column(String(60))
    # Marca ou fornecedor deste lote
    supplier_brand: Mapped[str] = mapped_column(String(120), nullable=False)
    # Preço pago por unidade de medida (kg/l/un) NESTE lote específico
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )

    # Quantidade original recebida e saldo restante (na unidade do ingrediente)
    initial_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Datas do fabricante: fabricação e validade — nulas para itens não
    # perecíveis (ex: embalagens)
    manufacturing_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date, index=True)

    # created_at (do TimestampMixin) registra a data de recebimento/entrada

    ingredient: Mapped["Ingredient"] = relationship(back_populates="lots")  # noqa: F821

    def is_expired(self, reference: date | None = None) -> bool:
        """Indica se o lote está vencido na data de referência (padrão: hoje)."""
        if self.expiration_date is None:
            return False
        return self.expiration_date < (reference or date.today())
