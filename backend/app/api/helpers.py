"""Helpers compartilhados pelas rotas da API."""
import uuid
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def get_tenant_entity_or_404(
    session: AsyncSession,
    model: type[T],
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    *,
    not_found_detail: str,
) -> T:
    """Busca a entidade SEMPRE filtrando por tenant e ignorando excluídas.

    Regras de ouro aplicadas em um único lugar: nenhuma query de dados de
    cliente roda sem tenant_id, e toda leitura ignora soft delete
    (deleted_at IS NULL).
    """
    entity = (
        await session.execute(
            select(model).where(
                model.id == entity_id,
                model.tenant_id == tenant_id,
                model.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return entity
