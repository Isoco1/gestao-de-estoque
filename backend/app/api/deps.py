"""Dependências compartilhadas das rotas (autenticação, tenant e RBAC).

MVP: o tenant é identificado pelo header `X-Tenant-ID` e o usuário pelo
header `X-User-ID`. Quando a autenticação JWT for implementada, os dois
virão das claims do token — as assinaturas `get_current_tenant` e
`get_current_user` permanecem, e nenhuma rota precisa mudar
(Dependency Inversion).

Regras aplicadas automaticamente:
  - Tenant BLOCKED  -> 403 em TODA rota protegida de tenant.
  - Rotas /admin    -> exigem usuário com role SUPER_ADMIN.
"""
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole

BLOCKED_TENANT_MESSAGE = (
    "Assinatura suspensa. Entre em contato com o suporte para regularizar o acesso."
)

# Sessão de banco por requisição
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} inválido")


async def get_current_tenant(
    session: SessionDep,
    x_tenant_id: Annotated[str | None, Header(description="UUID do tenant")] = None,
) -> Tenant:
    """Resolve e valida o tenant da requisição.

    Bloqueio de inadimplentes: se `status == BLOCKED`, a requisição morre
    aqui com 403 — nenhuma rota de tenant precisa repetir essa checagem.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Tenant-ID ausente",
        )
    tenant_uuid = _parse_uuid(x_tenant_id, "X-Tenant-ID")

    tenant = (
        await session.execute(
            select(Tenant).where(Tenant.id == tenant_uuid, Tenant.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    if tenant.status == TenantStatus.BLOCKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=BLOCKED_TENANT_MESSAGE)
    # PAST_DUE mantém o acesso (período de carência); o painel exibe avisos.
    return tenant


TenantDep = Annotated[Tenant, Depends(get_current_tenant)]


async def get_current_user_optional(
    session: SessionDep,
    x_user_id: Annotated[str | None, Header(description="UUID do usuário autenticado")] = None,
) -> User | None:
    """Resolve o usuário da requisição, quando informado.

    Opcional enquanto o login JWT não existe: rotas que registram auditoria
    usam o usuário se presente (ex: deleted_by).
    """
    if not x_user_id:
        return None
    user_uuid = _parse_uuid(x_user_id, "X-User-ID")
    return (
        await session.execute(
            select(User).where(User.id == user_uuid, User.is_active.is_(True))
        )
    ).scalar_one_or_none()


OptionalUserDep = Annotated[User | None, Depends(get_current_user_optional)]


async def get_super_admin(
    session: SessionDep,
    x_user_id: Annotated[str | None, Header(description="UUID do usuário autenticado")] = None,
) -> User:
    """Exige um usuário SUPER_ADMIN (painel administrativo da plataforma)."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-User-ID ausente",
        )
    user = await get_current_user_optional(session, x_user_id)
    if not user or user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao administrador da plataforma",
        )
    return user


SuperAdminDep = Annotated[User, Depends(get_super_admin)]


def require_roles(*roles: UserRole):
    """Fábrica de dependência RBAC para rotas de tenant.

    Uso futuro (com login obrigatório):
        @router.post("", dependencies=[Depends(require_roles(UserRole.TENANT_ADMIN))])
    Valida que o usuário autenticado pertence ao tenant da requisição e
    possui um dos papéis exigidos. SUPER_ADMIN sempre passa.
    """

    async def _checker(tenant: TenantDep, user: OptionalUserDep) -> User:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Header X-User-ID ausente",
            )
        if user.role == UserRole.SUPER_ADMIN:
            return user
        if user.tenant_id != tenant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário não pertence a este tenant",
            )
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente para esta operação",
            )
        return user

    return _checker
