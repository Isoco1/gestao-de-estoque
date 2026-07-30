"""Dependências compartilhadas das rotas.

MVP: o tenant é identificado pelo header `X-Tenant-ID`.
Próximo passo: substituir por autenticação JWT (o token carregará o
tenant_id na claim), mantendo a mesma assinatura `get_current_tenant`
para não quebrar as rotas (Dependency Inversion).
"""
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.tenant import Tenant

# Sessão de banco por requisição
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_tenant(
    session: SessionDep,
    x_tenant_id: Annotated[str | None, Header(description="UUID do tenant")] = None,
) -> Tenant:
    """Resolve e valida o tenant da requisição."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Tenant-ID ausente",
        )
    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Tenant-ID inválido")

    tenant = (
        await session.execute(
            select(Tenant).where(Tenant.id == tenant_uuid, Tenant.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")
    return tenant


TenantDep = Annotated[Tenant, Depends(get_current_tenant)]
