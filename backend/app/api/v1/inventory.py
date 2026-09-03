"""Visões consolidadas de estoque para o dashboard (alertas de vencimento)."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import SessionDep, TenantDep
from app.models.ingredient import Ingredient
from app.models.ingredient_lot import IngredientLot
from app.schemas.lot import ExpirationAlertItem, ExpirationAlertsRead

router = APIRouter(prefix="/inventory", tags=["Estoque"])


@router.get("/expiration-alerts", response_model=ExpirationAlertsRead)
async def expiration_alerts(
    session: SessionDep,
    tenant: TenantDep,
    days: int = Query(default=7, ge=1, le=365, description="Janela de dias para 'a vencer'"),
):
    """Lotes perecíveis com estoque parado, vencidos ou a vencer em `days` dias.

    - Vencidos: validade < hoje e saldo > 0 (dinheiro já em risco).
    - A vencer: validade entre hoje e hoje + days (agir antes de perder).
    Cada item traz a quantidade parada e o valor financeiro em risco (R$).
    """
    today = date.today()
    limit_date = today + timedelta(days=days)

    # Só as colunas usadas do ingrediente: carregar a entidade inteira
    # dispararia o selectin de TODOS os lotes de cada ingrediente.
    rows = (
        await session.execute(
            select(IngredientLot, Ingredient.id, Ingredient.name, Ingredient.unit)
            .join(Ingredient, IngredientLot.ingredient_id == Ingredient.id)
            .where(
                IngredientLot.tenant_id == tenant.id,
                IngredientLot.current_quantity > 0,
                IngredientLot.expiration_date.is_not(None),
                IngredientLot.expiration_date <= limit_date,
                # filtro padrão: ignora lotes/ingredientes excluídos
                IngredientLot.deleted_at.is_(None),
                Ingredient.deleted_at.is_(None),
            )
            .order_by(IngredientLot.expiration_date.asc())
        )
    ).all()

    expired: list[ExpirationAlertItem] = []
    expiring_soon: list[ExpirationAlertItem] = []
    total_value = Decimal("0")

    for lot, ingredient_id, ingredient_name, ingredient_unit in rows:
        value_at_risk = (lot.current_quantity * lot.unit_cost).quantize(Decimal("0.01"))
        total_value += value_at_risk
        item = ExpirationAlertItem(
            lot_id=lot.id,
            ingredient_id=ingredient_id,
            ingredient_name=ingredient_name,
            unit=ingredient_unit.value,
            supplier_brand=lot.supplier_brand,
            batch_number=lot.batch_number,
            expiration_date=lot.expiration_date,
            days_to_expiration=(lot.expiration_date - today).days,
            status="vencido" if lot.expiration_date < today else "a_vencer",
            quantity=lot.current_quantity,
            unit_cost=lot.unit_cost,
            value_at_risk=value_at_risk,
        )
        (expired if item.status == "vencido" else expiring_soon).append(item)

    return ExpirationAlertsRead(
        reference_date=today,
        days_window=days,
        expired=expired,
        expiring_soon=expiring_soon,
        total_value_at_risk=total_value,
    )
