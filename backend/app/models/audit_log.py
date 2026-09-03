"""Histórico imutável de ações sensíveis (exclusões, restaurações, etc.).

Cada registro guarda QUEM fez, O QUÊ, EM QUAL recurso e POR QUÊ
(justificativa obrigatória nas exclusões). Nunca é editado nem apagado.
"""
import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, uuid_pk
from app.models.user import User


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    # SET NULL preserva o log mesmo se o tenant/usuário for removido do banco
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Ação em maiúsculas, ex: "DELETE_INGREDIENT", "RESTORE_INGREDIENT"
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # Nome do recurso afetado, ex: "Ingredient"
    resource_name: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Justificativa preenchida pelo usuário (obrigatória nas exclusões)
    reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship(lazy="joined")
