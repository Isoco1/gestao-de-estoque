"""Mixins reutilizáveis para todos os modelos (DRY)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TimestampMixin:
    """Colunas de auditoria de criação/atualização."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Isolamento multi-tenant: toda tabela de dados possui tenant_id indexado.

    Regra de ouro: NENHUMA query de dados de cliente pode rodar sem
    filtrar por tenant_id.
    """

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805 - padrão SQLAlchemy
        return mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


def uuid_pk() -> Mapped[uuid.UUID]:
    """Chave primária UUID padrão do projeto (evita IDs sequenciais expostos)."""
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
