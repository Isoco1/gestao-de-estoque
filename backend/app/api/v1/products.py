"""CRUD de Produtos e gestão da Ficha Técnica (BOM)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import OptionalUserDep, SessionDep, TenantDep
from app.api.helpers import get_tenant_entity_or_404
from app.models.ingredient import Ingredient
from app.models.product import Product
from app.models.product_recipe import ProductRecipe
from app.schemas.common import SoftDeleteRequest
from app.schemas.product import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
    RecipeReplaceInput,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/products", tags=["Produtos e Ficha Técnica"])


async def _get_or_404(session: SessionDep, tenant_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    return await get_tenant_entity_or_404(
        session, Product, tenant_id, product_id,
        not_found_detail="Produto não encontrado",
    )


@router.get("", response_model=list[ProductRead])
async def list_products(session: SessionDep, tenant: TenantDep):
    stmt = (
        select(Product)
        .where(
            Product.tenant_id == tenant.id,
            Product.deleted_at.is_(None),  # filtro padrão: ignora excluídos
        )
        .order_by(Product.name)
    )
    return (await session.execute(stmt)).scalars().all()


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, session: SessionDep, tenant: TenantDep):
    # recipe_items=[] inicializa a coleção como carregada (produto novo não
    # tem ficha técnica), evitando lazy load async na serialização da resposta
    product = Product(tenant_id=tenant.id, recipe_items=[], **payload.model_dump())
    session.add(product)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um produto chamado '{payload.name}'",
        )
    # Sem refresh: expire_on_commit=False mantém a instância válida após o commit
    return product


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: uuid.UUID, session: SessionDep, tenant: TenantDep):
    return await _get_or_404(session, tenant.id, product_id)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID, payload: ProductUpdate, session: SessionDep, tenant: TenantDep
):
    product = await _get_or_404(session, tenant.id, product_id)
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field_name, value)
    await session.commit()
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    payload: SoftDeleteRequest,
    session: SessionDep,
    tenant: TenantDep,
    user: OptionalUserDep,
):
    """Exclusão lógica com justificativa obrigatória (mesmo fluxo dos ingredientes).

    O produto sai do cardápio, mas o histórico de vendas permanece; a
    exclusão preenche deleted_at/deleted_by/reason e grava o AuditLog
    na mesma transação. Restauração: painel SUPER_ADMIN.
    """
    product = await _get_or_404(session, tenant.id, product_id)

    product.deleted_at = datetime.now(timezone.utc)
    product.deleted_by_id = user.id if user else None
    product.deletion_reason = payload.reason
    log_action(
        session,
        tenant_id=tenant.id,
        user=user,
        action="DELETE_PRODUCT",
        resource_name="Product",
        resource_id=product.id,
        reason=payload.reason,
    )
    await session.commit()


@router.put("/{product_id}/recipe", response_model=ProductRead)
async def replace_recipe(
    product_id: uuid.UUID, payload: RecipeReplaceInput, session: SessionDep, tenant: TenantDep
):
    """Substitui a ficha técnica completa do produto.

    Estratégia "replace all" simplifica o frontend: a tela monta a lista
    final e envia de uma vez, sem diffs item a item.
    """
    product = await _get_or_404(session, tenant.id, product_id)

    # Valida que todos os ingredientes pertencem ao tenant
    ingredient_ids = [item.ingredient_id for item in payload.items]
    if len(set(ingredient_ids)) != len(ingredient_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ingrediente duplicado na ficha técnica",
        )
    if ingredient_ids:
        found = (
            await session.execute(
                select(Ingredient.id).where(
                    Ingredient.tenant_id == tenant.id, Ingredient.id.in_(ingredient_ids)
                )
            )
        ).scalars().all()
        missing = set(ingredient_ids) - set(found)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Ingredientes inexistentes: {[str(m) for m in missing]}",
            )

    # Remove itens antigos e insere os novos (transação única)
    product.recipe_items.clear()
    await session.flush()
    for item in payload.items:
        session.add(
            ProductRecipe(
                tenant_id=tenant.id,
                product_id=product.id,
                ingredient_id=item.ingredient_id,
                quantity=item.quantity,
            )
        )
    await session.commit()

    # Força o recarregamento da coleção: com expire_on_commit=False a
    # instância em cache ainda apontaria para a lista antiga (vazia).
    await session.refresh(product, ["recipe_items"])
    return product
