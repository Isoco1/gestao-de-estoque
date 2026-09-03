"""Painel administrativo da plataforma — EXCLUSIVO para SUPER_ADMIN.

Todas as rotas deste router exigem o header X-User-ID de um usuário com
role SUPER_ADMIN (dependência get_super_admin aplicada no router inteiro).
Estas rotas atravessam tenants — por isso não usam TenantDep.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import SessionDep, SuperAdminDep, get_super_admin
from app.models.ingredient import Ingredient
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.admin import DeletedByRead, DeletedIngredientRead
from app.schemas.ingredient import IngredientRead
from app.services.audit_service import log_action

router = APIRouter(
    prefix="/admin",
    tags=["Admin (SUPER_ADMIN)"],
    dependencies=[Depends(get_super_admin)],
)


@router.get(
    "/tenants/{tenant_id}/deleted-ingredients",
    response_model=list[DeletedIngredientRead],
)
async def list_deleted_ingredients(tenant_id: uuid.UUID, session: SessionDep):
    """Ingredientes excluídos do tenant: quem deletou, quando e por quê."""
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    rows = (
        await session.execute(
            select(Ingredient, User)
            .outerjoin(User, User.id == Ingredient.deleted_by_id)
            .where(
                Ingredient.tenant_id == tenant_id,
                Ingredient.deleted_at.is_not(None),
            )
            .order_by(Ingredient.deleted_at.desc())
        )
    ).all()

    return [
        DeletedIngredientRead(
            id=ingredient.id,
            name=ingredient.name,
            unit=ingredient.unit,
            deleted_at=ingredient.deleted_at,
            deletion_reason=ingredient.deletion_reason,
            deleted_by=DeletedByRead.model_validate(deleted_by) if deleted_by else None,
        )
        for ingredient, deleted_by in rows
    ]


@router.post("/ingredients/{ingredient_id}/restore", response_model=IngredientRead)
async def restore_ingredient(
    ingredient_id: uuid.UUID, session: SessionDep, admin: SuperAdminDep
):
    """Restaura um ingrediente excluído (deleted_at volta a NULL) com auditoria."""
    ingredient = (
        await session.execute(
            select(Ingredient).where(
                Ingredient.id == ingredient_id,
                Ingredient.deleted_at.is_not(None),
            )
        )
    ).scalar_one_or_none()
    if not ingredient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingrediente não encontrado ou não está excluído",
        )

    original_reason = ingredient.deletion_reason
    ingredient.deleted_at = None
    ingredient.deleted_by_id = None
    ingredient.deletion_reason = None
    log_action(
        session,
        tenant_id=ingredient.tenant_id,
        user=admin,
        action="RESTORE_INGREDIENT",
        resource_name="Ingredient",
        resource_id=ingredient.id,
        reason=f"Restauração via painel admin (exclusão original: {original_reason})",
    )
    await session.commit()
    await session.refresh(ingredient, ["lots"])
    return ingredient
