"""Serviço de baixa de estoque por lotes com estratégia FEFO.

FEFO (First Expired, First Out): a baixa consome primeiro o lote com a
data de validade mais próxima; se ele não bastar, segue para o próximo.
Lotes VENCIDOS não são consumidos em vendas (não se vende produto vencido);
perdas/descartes manuais podem consumi-los (include_expired=True).

Fluxo da venda (tudo dentro de UMA transação — ACID):
  1. Localiza os produtos vendidos e suas fichas técnicas.
  2. Agrega a necessidade total de cada ingrediente.
  3. Trava os LOTES dos ingredientes (SELECT ... FOR UPDATE) para evitar
     condição de corrida entre webhooks simultâneos.
  4. Valida disponibilidade, baixa lote a lote (FEFO) e grava um
     StockMovement por fatia consumida (rastreabilidade por lote).
  5. Cria Order + OrderItems.
Qualquer erro dispara rollback automático — nada é baixado pela metade.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredient import Ingredient
from app.models.ingredient_lot import IngredientLot
from app.models.order import Order, OrderItem, OrderSource, OrderStatus
from app.models.product import Product
from app.models.product_recipe import ProductRecipe
from app.models.stock_movement import MovementType, StockMovement
from app.services.order_parser import ParsedItem


class InsufficientStockError(Exception):
    """Estoque insuficiente para concluir a operação."""

    def __init__(self, shortages: list[str]) -> None:
        self.shortages = shortages
        super().__init__("Estoque insuficiente: " + "; ".join(shortages))


@dataclass
class SaleResult:
    """Resultado da venda processada, usado para respostas e alertas."""

    order_id: uuid.UUID
    matched_items: list[tuple[str, int]] = field(default_factory=list)      # (produto, qtd)
    unmatched_names: list[str] = field(default_factory=list)                # nomes não reconhecidos
    low_stock_items: list[dict] = field(default_factory=list)               # p/ alerta ao gerente


def _fefo_order(lots: list[IngredientLot]) -> list[IngredientLot]:
    """Ordena lotes para consumo: validade mais próxima primeiro,
    sem validade por último; empate resolvido pelo mais antigo."""
    return sorted(
        lots,
        key=lambda lot: (
            lot.expiration_date is None,   # com validade antes dos sem validade
            lot.expiration_date or date.max,
            lot.created_at,
        ),
    )


def _consume_lots_fefo(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    lots: list[IngredientLot],
    quantity: Decimal,
    running_total: Decimal,
    movement_type: MovementType,
    origin: str,
    order_id: uuid.UUID | None = None,
    include_expired: bool = False,
) -> Decimal:
    """Baixa `quantity` dos lotes em ordem FEFO, gravando um StockMovement
    por fatia. `running_total` é o saldo total do ingrediente antes da baixa;
    retorna o saldo total após. Pré-condição: os lotes já estão travados
    (FOR UPDATE) e a disponibilidade já foi validada pelo chamador.
    """
    remaining = quantity
    for lot in _fefo_order(lots):
        if remaining <= 0:
            break
        if lot.current_quantity <= 0:
            continue
        if not include_expired and lot.is_expired():
            continue

        slice_qty = min(lot.current_quantity, remaining)
        lot.current_quantity -= slice_qty
        remaining -= slice_qty
        running_total -= slice_qty
        session.add(
            StockMovement(
                tenant_id=tenant_id,
                ingredient_id=ingredient_id,
                lot_id=lot.id,
                type=movement_type,
                quantity=-slice_qty,
                balance_after=running_total,
                origin=origin,
                order_id=order_id,
            )
        )

    if remaining > 0:
        # Nunca deve acontecer se o chamador validou a disponibilidade
        raise InsufficientStockError([f"lote insuficiente para o ingrediente {ingredient_id}"])
    return running_total


async def _match_products(
    session: AsyncSession, tenant_id: uuid.UUID, parsed_items: list[ParsedItem]
) -> tuple[list[tuple[Product, int]], list[str]]:
    """Mapeia nomes livres da mensagem para produtos do tenant (case-insensitive)."""
    matched: list[tuple[Product, int]] = []
    unmatched: list[str] = []

    for item in parsed_items:
        stmt = select(Product).where(
            Product.tenant_id == tenant_id,
            Product.is_active.is_(True),
            func.lower(Product.name) == item.product_name.lower(),
        )
        product = (await session.execute(stmt)).scalar_one_or_none()
        if product:
            matched.append((product, item.quantity))
        else:
            unmatched.append(item.product_name)
    return matched, unmatched


async def _lock_lots(
    session: AsyncSession, tenant_id: uuid.UUID, ingredient_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[IngredientLot]]:
    """Trava (FOR UPDATE) todos os lotes com saldo dos ingredientes dados.

    A ordenação estável por (ingredient_id, id) faz transações concorrentes
    adquirirem os locks na mesma ordem, prevenindo deadlock.
    """
    if not ingredient_ids:
        return {}
    stmt = (
        select(IngredientLot)
        .where(
            IngredientLot.tenant_id == tenant_id,
            IngredientLot.ingredient_id.in_(ingredient_ids),
            IngredientLot.current_quantity > 0,
        )
        .order_by(IngredientLot.ingredient_id, IngredientLot.id)
        .with_for_update()
    )
    lots_by_ingredient: dict[uuid.UUID, list[IngredientLot]] = {}
    for lot in (await session.execute(stmt)).scalars().all():
        lots_by_ingredient.setdefault(lot.ingredient_id, []).append(lot)
    return lots_by_ingredient


async def process_sale(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    parsed_items: list[ParsedItem],
    *,
    source: OrderSource,
    customer_phone: str | None = None,
    raw_message: str | None = None,
) -> SaleResult:
    """Executa a venda com baixa de estoque FEFO atômica.

    O chamador é responsável por `session.commit()` em caso de sucesso;
    exceções aqui levantadas devem provocar rollback no chamador.
    """
    matched, unmatched = await _match_products(session, tenant_id, parsed_items)
    if not matched:
        raise ValueError("Nenhum produto da mensagem foi reconhecido no cardápio")

    # ---- 1. Agrega a necessidade total por ingrediente (BOM x quantidade) ----
    needs: dict[uuid.UUID, Decimal] = {}
    for product, qty in matched:
        recipe = (
            await session.execute(
                select(ProductRecipe).where(
                    ProductRecipe.tenant_id == tenant_id,
                    ProductRecipe.product_id == product.id,
                )
            )
        ).scalars().all()
        for recipe_item in recipe:
            needs[recipe_item.ingredient_id] = (
                needs.get(recipe_item.ingredient_id, Decimal("0"))
                + recipe_item.quantity * qty
            )

    # Metadados dos ingredientes (nome/unidade/mínimo) — sem lock: quem é
    # travado agora são os LOTES, a fonte de verdade do saldo.
    ingredients: dict[uuid.UUID, Ingredient] = {}
    if needs:
        rows = (
            await session.execute(
                select(Ingredient).where(
                    Ingredient.tenant_id == tenant_id, Ingredient.id.in_(needs.keys())
                )
            )
        ).scalars().all()
        ingredients = {ing.id: ing for ing in rows}

    # ---- 2. Trava os lotes e valida a disponibilidade (sem lotes vencidos) ----
    lots_by_ingredient = await _lock_lots(session, tenant_id, list(needs.keys()))

    shortages: list[str] = []
    for ing_id, needed in needs.items():
        ing = ingredients[ing_id]
        # Ingrediente excluído (soft delete) não pode compor vendas
        if ing.is_deleted:
            shortages.append(f"{ing.name} (ingrediente excluído do estoque)")
            continue
        available = sum(
            (lot.current_quantity for lot in lots_by_ingredient.get(ing_id, [])
             if not lot.is_expired()),
            Decimal("0"),
        )
        if available < needed:
            shortages.append(
                f"{ing.name} (precisa {needed} {ing.unit.value}, disponível {available})"
            )
    if shortages:
        raise InsufficientStockError(shortages)

    # ---- 3. Cria a venda ----
    order = Order(
        tenant_id=tenant_id,
        source=source,
        status=OrderStatus.PROCESSED,
        customer_phone=customer_phone,
        raw_message=raw_message,
        total=sum((p.price * qty for p, qty in matched), Decimal("0")),
    )
    session.add(order)
    await session.flush()  # garante order.id para os vínculos abaixo

    for product, qty in matched:
        session.add(
            OrderItem(
                tenant_id=tenant_id,
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=product.price,
            )
        )

    # ---- 4. Baixa FEFO lote a lote + movimentações ----
    origin_label = "Venda WhatsApp" if source == OrderSource.WHATSAPP else "Venda Manual"
    movement_type = (
        MovementType.SALE_WHATSAPP if source == OrderSource.WHATSAPP else MovementType.SALE_MANUAL
    )
    low_stock: list[dict] = []
    for ing_id, needed in needs.items():
        ing = ingredients[ing_id]
        lots = lots_by_ingredient.get(ing_id, [])
        total_before = sum((lot.current_quantity for lot in lots), Decimal("0"))
        total_after = _consume_lots_fefo(
            session,
            tenant_id=tenant_id,
            ingredient_id=ing_id,
            lots=lots,
            quantity=needed,
            running_total=total_before,
            movement_type=movement_type,
            origin=origin_label,
            order_id=order.id,
        )
        if total_after <= ing.min_stock:
            low_stock.append(
                {
                    "name": ing.name,
                    "stock": total_after,
                    "min": ing.min_stock,
                    "unit": ing.unit.value,
                }
            )

    return SaleResult(
        order_id=order.id,
        matched_items=[(p.name, qty) for p, qty in matched],
        unmatched_names=unmatched,
        low_stock_items=low_stock,
    )


async def register_loss(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    ingredient: Ingredient,
    quantity: Decimal,
    *,
    origin: str,
) -> Decimal:
    """Registra perda/descarte manual com baixa FEFO.

    Diferente da venda, CONSOME lotes vencidos (é justamente o caso de uso
    de descartar produto vencido). Retorna o saldo total após a baixa.
    O chamador é responsável pelo commit/rollback.
    """
    lots_by_ingredient = await _lock_lots(session, tenant_id, [ingredient.id])
    lots = lots_by_ingredient.get(ingredient.id, [])
    total_before = sum((lot.current_quantity for lot in lots), Decimal("0"))
    if total_before < quantity:
        raise InsufficientStockError(
            [f"{ingredient.name} (baixa de {quantity}, saldo {total_before})"]
        )
    return _consume_lots_fefo(
        session,
        tenant_id=tenant_id,
        ingredient_id=ingredient.id,
        lots=lots,
        quantity=quantity,
        running_total=total_before,
        movement_type=MovementType.LOSS,
        origin=origin,
        include_expired=True,
    )
