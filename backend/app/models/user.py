"""Usuário do painel. Usuários de tenant possuem tenant_id; o SUPER_ADMIN
da plataforma tem tenant_id nulo (acesso global)."""
import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, uuid_pk


class UserRole(str, enum.Enum):
    """Papéis de acesso (RBAC).

    SUPER_ADMIN  -> operador da plataforma: acesso global a todos os
                    tenants e ao painel administrativo (/admin)
    TENANT_ADMIN -> dono do restaurante: gerencia o próprio tenant,
                    usuários e estoque
    TENANT_USER  -> funcionário/operador: apenas rotas operacionais
    """

    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    TENANT_USER = "tenant_user"


class User(Base, TimestampMixin):
    __tablename__ = "users"
    # E-mail único por tenant (o mesmo e-mail pode existir em tenants diferentes)
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    # Nulo apenas para SUPER_ADMIN (usuário da plataforma, sem tenant)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [x.value for x in e]),
        default=UserRole.TENANT_USER,
        server_default=UserRole.TENANT_USER.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
