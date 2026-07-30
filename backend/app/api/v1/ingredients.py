"""CRUD de Ingredientes + gestão de Lotes (validade/fornecedor) + lançamentos."""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep, TenantDep
from app.models.ingredient import Ingredient
from app.models.ingredient_lot import IngredientLot
from app.models.stock_movement import MovementType, StockMovement
from app.schemas.ingredient import (
    IngredientCreate,
    IngredientRead,
    IngredientUpdate,
    StockEntryCreate,
)
from app.schemas.lot import IngredientLotsRead, LotCreate, LotRead
from app.services.stock_service import InsufficientStockError, register_loss

router = APIRouter(prefix="/ingredients", tags=["Ingredientes"])


async def _get_or_404(session: SessionDep, tenant_id: uuid.UUID, ingredient_id: uuid.UUID) -> Ingredient:
    """Busca o ingrediente SEMPRE filtrando por tenant (isolamento)."""
    ingredient = (
        await session.execute(
            select(Ingredient).where(
                Ingredient.id == ingredient_id, Ingredient.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not ingredient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente não encontrado")
    return ingredient


def _add_lot(
    session: SessionDep,
    ingredient: Ingredient,
    *,
    quantity: Decimal,
    supplier_brand: str,
    unit_cost: Decimal = Decimal("0"),
    batch_number: str | None = None,
    manufacturing_date: date | None = None,
    expiration_date: date | None = None,
    origin: str,
    balance_after: Decimal,
) -> IngredientLot:
    """Cria um lote + a movimentação de entrada correspondente (DRY)."""
    lot = IngredientLot(
        id=uuid.uuid4(),  # id explícito para vincular a movimentação antes do flush
        tenant_id=ingredient.tenant_id,
        ingredient_id=ingredient.id,
        batch_number=batch_number,
        supplier_brand=supplier_brand,
        unit_cost=unit_cost,
        initial_quantity=quantity,
        current_quantity=quantity,
        manufacturing_date=manufacturing_date,
        expiration_date=expiration_date,
    )
    session.add(lot)
    session.add(
        StockMovement(
            tenant_id=ingredient.tenant_id,
            ingredient_id=ingredient.id,
            lot_id=lot.id,
            type=MovementType.ENTRY,
            quantity=quantity,
            balance_after=balance_after,
            origin=origin,
        )
    )
    return lot


@router.get("", response_model=list[IngredientRead])
async def list_ingredients(session: SessionDep, tenant: TenantDep, only_critical: bool = False):
    """Lista ingredientes; `only_critical=true` retorna apenas estoque crítico."""
    stmt = select(Ingredient).where(
        Ingredient.tenant_id == tenant.id, Ingredient.is_active.is_(True)
    )
    if only_critical:
        # Estoque total = soma dos lotes com saldo (subquery correlacionada)
        total_subquery = (
            select(func.coalesce(func.sum(IngredientLot.current_quantity), 0))
            .where(
                IngredientLot.ingredient_id == Ingredient.id,
                IngredientLot.current_quantity > 0,
            )
            .correlate(Ingredient)
            .scalar_subquery()
        )
        stmt = stmt.where(total_subquery <= Ingredient.min_stock)
    stmt = stmt.order_by(Ingredient.name)
    return (await session.execute(stmt)).scalars().all()


@router.post("", response_model=IngredientRead, status_code=status.HTTP_201_CREATED)
async def create_ingredient(payload: IngredientCreate, session: SessionDep, tenant: TenantDep):
    data = payload.model_dump()
    initial_quantity = data.pop("stock_quantity")
    ingredient = Ingredient(tenant_id=tenant.id, **data)
    session.add(ingredient)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um ingrediente chamado '{payload.name}'",
        )

    # A carga inicial vira o primeiro lote (rastreabilidade desde o cadastro)
    if initial_quantity > 0:
        _add_lot(
            session,
            ingredient,
            quantity=initial_quantity,
            supplier_brand="Estoque inicial",
            unit_cost=payload.cost_per_unit or Decimal("0"),
            origin="Cadastro inicial",
            balance_after=initial_quantity,
        )
    await session.commit()
    await session.refresh(ingredient, ["lots"])
    return ingredient


@router.get("/{ingredient_id}", response_model=IngredientRead)
async def get_ingredient(ingredient_id: uuid.UUID, session: SessionDep, tenant: TenantDep):
    return await _get_or_404(session, tenant.id, ingredient_id)


@router.patch("/{ingredient_id}", response_model=IngredientRead)
async def update_ingredient(
    ingredient_id: uuid.UUID, payload: IngredientUpdate, session: SessionDep, tenant: TenantDep
):
    ingredient = await _get_or_404(session, tenant.id, ingredient_id)
    # exclude_unset: só altera o que o cliente realmente enviou (PATCH parcial)
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(ingredient, field_name, value)
    await session.commit()
    await session.refresh(ingredient)
    return ingredient


@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_ingredient(ingredient_id: uuid.UUID, session: SessionDep, tenant: TenantDep):
    """Soft delete: preserva o histórico de movimentações e fichas técnicas."""
    ingredient = await _get_or_404(session, tenant.id, ingredient_id)
    ingredient.is_active = False
    await session.commit()


# ---------------------------------------------------------------------------
# Lotes (janela de detalhes do ingrediente)
# ---------------------------------------------------------------------------

@router.get("/{ingredient_id}/lots", response_model=IngredientLotsRead)
async def list_lots(ingredient_id: uuid.UUID, session: SessionDep, tenant: TenantDep):
    """Ingrediente + todos os lotes (ativos e zerados) + métricas consolidadas.

    Ordenação: validade mais próxima primeiro; sem validade por último.
    """
    ingredient = await _get_or_404(session, tenant.id, ingredient_id)
    lots = (
        await session.execute(
            select(IngredientLot)
            .where(
                IngredientLot.tenant_id == tenant.id,
                IngredientLot.ingredient_id == ingredient.id,
            )
            .order_by(
                IngredientLot.expiration_date.asc().nulls_last(),
                IngredientLot.created_at.asc(),
            )
        )
    ).scalars().all()

    return IngredientLotsRead(
        ingredient=IngredientRead.model_validate(ingredient),
        lots=[LotRead.model_validate(lot) for lot in lots],
        total_quantity=ingredient.total_quantity,
        weighted_average_cost=ingredient.weighted_average_cost,
    )


@router.post(
    "/{ingredient_id}/lots", response_model=LotRead, status_code=status.HTTP_201_CREATED
)
async def create_lot(
    ingredient_id: uuid.UUID, payload: LotCreate, session: SessionDep, tenant: TenantDep
):
    """Registra a chegada de um novo lote e a movimentação de entrada."""
    ingredient = await _get_or_404(session, tenant.id, ingredient_id)

    if payload.expiration_date and payload.expiration_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Data de validade no passado — confira o lote recebido",
        )
    if payload.manufacturing_date and payload.manufacturing_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Data de fabricação no futuro — confira o lote recebido",
        )

    lot = _add_lot(
        session,
        ingredient,
        quantity=payload.quantity,
        supplier_brand=payload.supplier_brand,
        unit_cost=payload.unit_cost,
        batch_number=payload.batch_number,
        manufacturing_date=payload.manufacturing_date,
        expiration_date=payload.expiration_date,
        origin=f"Entrada de lote — {payload.supplier_brand}",
        balance_after=ingredient.total_quantity + payload.quantity,
    )
    await session.commit()
    await session.refresh(lot)
    return lot


# ---------------------------------------------------------------------------
# Lançamento manual simples (entrada avulsa / perda)
# ---------------------------------------------------------------------------

@router.post("/{ingredient_id}/stock-entries", response_model=IngredientRead)
async def add_stock_entry(
    ingredient_id: uuid.UUID, payload: StockEntryCreate, session: SessionDep, tenant: TenantDep
):
    """Lançamento manual: positivo = entrada (vira lote avulso);
    negativo = perda/descarte com baixa FEFO (incluindo lotes vencidos)."""
    if payload.quantity == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantidade não pode ser zero")

    ingredient = await _get_or_404(session, tenant.id, ingredient_id)

    if payload.quantity > 0:
        _add_lot(
            session,
            ingredient,
            quantity=payload.quantity,
            supplier_brand="Entrada avulsa",
            unit_cost=ingredient.cost_per_unit or Decimal("0"),
            origin=payload.note or "Lançamento manual",
            balance_after=ingredient.total_quantity + payload.quantity,
        )
    else:
        try:
            await register_loss(
                session,
                tenant.id,
                ingredient,
                -payload.quantity,
                origin=payload.note or "Perda/ajuste manual",
            )
        except InsufficientStockError:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Operação deixaria o estoque negativo",
            )

    await session.commit()
    await session.refresh(ingredient, ["lots"])
    return ingredient
