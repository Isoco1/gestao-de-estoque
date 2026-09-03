"""Mixins reutilizáveis para todos os modelos (DRY)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
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


class SoftDeleteMixin:
    """Exclusão lógica com trilha de auditoria.

    Regra de ouro: NUNCA executar DELETE físico em tabelas críticas.
    A "exclusão" preenche deleted_at/deleted_by_id/deletion_reason, e
    TODA listagem deve filtrar `deleted_at IS NULL`.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    @declared_attr
    def deleted_by_id(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805 - padrão SQLAlchemy
        return mapped_column(
            Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        )

    deletion_reason: Mapped[str | None] = mapped_column(Text, default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def uuid_pk() -> Mapped[uuid.UUID]:
    """Chave primária UUID padrão do projeto (evita IDs sequenciais expostos)."""
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
