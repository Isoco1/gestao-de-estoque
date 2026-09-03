"""Tenant = cliente do SaaS (restaurante, delivery ou mercado)."""
import enum
import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, uuid_pk


class TenantStatus(str, enum.Enum):
    """Status de assinatura do tenant (controla o acesso à API).

    ACTIVE   -> acesso normal
    PAST_DUE -> em atraso: acesso mantido (período de carência), painel
                pode exibir avisos de regularização
    BLOCKED  -> inadimplente: TODA rota de tenant responde 403
    """

    ACTIVE = "active"
    PAST_DUE = "past_due"
    BLOCKED = "blocked"


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Status de cobrança/assinatura — checado em toda requisição autenticada
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", values_callable=lambda e: [x.value for x in e]),
        default=TenantStatus.ACTIVE,
        server_default=TenantStatus.ACTIVE.value,
        nullable=False,
    )

    # Credenciais Z-API do tenant. O instance_id identifica o tenant
    # quando o webhook chega (cada instância Z-API = um número de WhatsApp).
    zapi_instance_id: Mapped[str | None] = mapped_column(
        String(80), unique=True, index=True
    )
    zapi_instance_token: Mapped[str | None] = mapped_column(String(120))

    # WhatsApp do gerente para receber alertas de estoque baixo
    manager_phone: Mapped[str | None] = mapped_column(String(20))
