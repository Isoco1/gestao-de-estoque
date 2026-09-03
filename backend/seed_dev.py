"""Popula o banco com dados de demonstração para desenvolvimento.

Uso:  python seed_dev.py
Cria 1 tenant ("Pizzaria Demo"), ingredientes com LOTES (validade e
fornecedor), produtos e a ficha técnica da Pizza Calabresa
(300g massa + 150g queijo + 100g calabresa + 1 embalagem).

Cenários incluídos para demonstrar as novas funcionalidades:
  - Queijo com 2 lotes de validades diferentes -> baixa FEFO.
  - Lote de calabresa vencendo em 3 dias        -> alerta "a vencer".
  - Lote de massa já vencido com saldo          -> alerta "vencido".

Imprime o tenant_id para usar no header X-Tenant-ID e no frontend.
"""
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, Base, engine
from app.models import (
    Ingredient,
    IngredientLot,
    MeasureUnit,
    MovementType,
    Product,
    ProductRecipe,
    StockMovement,
    Tenant,
    User,
    UserRole,
)


async def _ensure_users(session, tenant: Tenant) -> None:
    """Garante os usuários de demonstração (idempotente).

    Sem login JWT ainda: as senhas são placeholders. Os IDs impressos
    servem para o header X-User-ID (painel admin e auditoria).
    """
    super_admin = (
        await session.execute(select(User).where(User.role == UserRole.SUPER_ADMIN))
    ).scalars().first()
    if not super_admin:
        super_admin = User(
            tenant_id=None,  # SUPER_ADMIN é global (sem tenant)
            name="Admin da Plataforma",
            email="admin@plataforma.local",
            hashed_password="!definir-com-jwt",
            role=UserRole.SUPER_ADMIN,
        )
        session.add(super_admin)

    owner = (
        await session.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == "dono@pizzariademo.local")
        )
    ).scalar_one_or_none()
    if not owner:
        owner = User(
            tenant_id=tenant.id,
            name="Dono da Pizzaria",
            email="dono@pizzariademo.local",
            hashed_password="!definir-com-jwt",
            role=UserRole.TENANT_ADMIN,
        )
        session.add(owner)

    await session.commit()
    print(f"SUPER_ADMIN User ID (header X-User-ID): {super_admin.id}")
    print(f"TENANT_ADMIN User ID (header X-User-ID): {owner.id}")


def _lot(
    tenant_id,
    ingredient: Ingredient,
    quantity: str,
    *,
    supplier: str,
    cost: str = "0",
    batch: str | None = None,
    expires_in_days: int | None = None,
) -> list:
    """Cria um lote + movimentação de entrada para o seed."""
    import uuid as _uuid

    expiration = (
        date.today() + timedelta(days=expires_in_days) if expires_in_days is not None else None
    )
    lot = IngredientLot(
        id=_uuid.uuid4(),
        tenant_id=tenant_id,
        ingredient_id=ingredient.id,
        batch_number=batch,
        supplier_brand=supplier,
        unit_cost=Decimal(cost),
        initial_quantity=Decimal(quantity),
        current_quantity=Decimal(quantity),
        expiration_date=expiration,
    )
    movement = StockMovement(
        tenant_id=tenant_id,
        ingredient_id=ingredient.id,
        lot_id=lot.id,
        type=MovementType.ENTRY,
        quantity=Decimal(quantity),
        balance_after=Decimal(quantity),  # aproximação suficiente para seed
        origin=f"Seed — {supplier}",
    )
    return [lot, movement]


async def seed() -> None:
    # Em dev, cria as tabelas direto do metadata caso o Alembic ainda não tenha rodado
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(select(Tenant).where(Tenant.slug == "pizzaria-demo"))
        ).scalar_one_or_none()
        if existing:
            print(f"Seed já executado. Tenant ID: {existing.id}")
            await _ensure_users(session, existing)
            return

        tenant = Tenant(
            name="Pizzaria Demo",
            slug="pizzaria-demo",
            zapi_instance_id="DEMO_INSTANCE_123",
            zapi_instance_token="DEMO_TOKEN",
            manager_phone="5511999999999",
        )
        session.add(tenant)
        await session.flush()

        massa = Ingredient(
            tenant_id=tenant.id, name="Massa", unit=MeasureUnit.G, min_stock=Decimal("2000"),
        )
        queijo = Ingredient(
            tenant_id=tenant.id, name="Queijo Muçarela", unit=MeasureUnit.G, min_stock=Decimal("1000"),
        )
        calabresa = Ingredient(
            tenant_id=tenant.id, name="Calabresa", unit=MeasureUnit.G, min_stock=Decimal("500"),
        )
        embalagem = Ingredient(
            tenant_id=tenant.id, name="Embalagem Pizza", unit=MeasureUnit.UN, min_stock=Decimal("10"),
        )
        session.add_all([massa, queijo, calabresa, embalagem])
        await session.flush()

        # ---- Lotes (validade, fornecedor e custo por lote) ----
        objects: list = []
        # Massa: lote saudável + lote VENCIDO com saldo (demonstra alerta "vencido")
        objects += _lot(tenant.id, massa, "9500", supplier="Moinho Bom Trigo",
                        cost="0.008", batch="MT-2031", expires_in_days=30)
        objects += _lot(tenant.id, massa, "500", supplier="Moinho Bom Trigo",
                        cost="0.008", batch="MT-1980", expires_in_days=-2)
        # Queijo: 2 lotes com validades diferentes (demonstra FEFO)
        objects += _lot(tenant.id, queijo, "2000", supplier="Laticínios Serra Azul",
                        cost="0.045", batch="SA-778", expires_in_days=5)
        objects += _lot(tenant.id, queijo, "3000", supplier="Queijos Bela Vista",
                        cost="0.040", batch="BV-102", expires_in_days=20)
        # Calabresa: lote vencendo em 3 dias (demonstra alerta "a vencer")
        objects += _lot(tenant.id, calabresa, "3000", supplier="Frigorífico Boi Feliz",
                        cost="0.030", batch="BF-455", expires_in_days=3)
        # Embalagem: não perecível (sem validade)
        objects += _lot(tenant.id, embalagem, "50", supplier="Embalagens Rápidas",
                        cost="1.20")
        session.add_all(objects)

        pizza = Product(tenant_id=tenant.id, name="Pizza Calabresa", price=Decimal("49.90"))
        session.add(pizza)
        await session.flush()

        session.add_all([
            ProductRecipe(tenant_id=tenant.id, product_id=pizza.id,
                          ingredient_id=massa.id, quantity=Decimal("300")),
            ProductRecipe(tenant_id=tenant.id, product_id=pizza.id,
                          ingredient_id=queijo.id, quantity=Decimal("150")),
            ProductRecipe(tenant_id=tenant.id, product_id=pizza.id,
                          ingredient_id=calabresa.id, quantity=Decimal("100")),
            ProductRecipe(tenant_id=tenant.id, product_id=pizza.id,
                          ingredient_id=embalagem.id, quantity=Decimal("1")),
        ])

        await session.commit()
        print("Seed concluído!")
        print(f"Tenant ID (use no header X-Tenant-ID): {tenant.id}")
        await _ensure_users(session, tenant)


if __name__ == "__main__":
    asyncio.run(seed())
