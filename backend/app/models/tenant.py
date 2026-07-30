"""Tenant = cliente do SaaS (restaurante, delivery ou mercado)."""
import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, uuid_pk


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Credenciais Z-API do tenant. O instance_id identifica o tenant
    # quando o webhook chega (cada instância Z-API = um número de WhatsApp).
    zapi_instance_id: Mapped[str | None] = mapped_column(
        String(80), unique=True, index=True
    )
    zapi_instance_token: Mapped[str | None] = mapped_column(String(120))

    # WhatsApp do gerente para receber alertas de estoque baixo
    manager_phone: Mapped[str | None] = mapped_column(String(20))
