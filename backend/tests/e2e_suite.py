"""Suite E2E de verificacao do estoque-saas (TestClient + SQLite).

Rodar com o venv do backend:
    .venv\\Scripts\\python.exe tests\\e2e_suite.py

Cobre: venda FEFO via webhook Z-API, lotes vencidos (nao consumidos em venda),
atomicidade em estoque insuficiente, alerta de estoque baixo, alertas de
vencimento, soft delete de ingrediente (justificativa + admin restore),
exclusao de produto e RBAC do painel admin.
"""
import os
import sys
import sqlite3
import tempfile
from datetime import date, timedelta

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(tempfile.gettempdir(), "estoque_saas_e2e.db")

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"
os.environ["ZAPI_BASE_URL"] = "http://127.0.0.1:9"  # falha instantanea, sem rede
os.environ["ZAPI_CLIENT_TOKEN"] = "test-token"
os.environ["ENVIRONMENT"] = "test"  # desliga echo de SQL

sys.path.insert(0, BACKEND)

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

import asyncio  # noqa: E402
import uuid  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine, AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tenant, User, UserRole  # noqa: E402

TENANT_ID = uuid.uuid4()
SUPER_ADMIN_ID = uuid.uuid4()
TENANT_USER_ID = uuid.uuid4()


async def _setup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        session.add(
            Tenant(
                id=TENANT_ID,
                name="Pizzaria Teste",
                slug="pizzaria-teste",
                zapi_instance_id="inst-1",
                zapi_instance_token="tok-1",
                manager_phone="5511900000000",
            )
        )
        session.add(
            User(
                id=SUPER_ADMIN_ID,
                tenant_id=None,
                name="Root",
                email="root@plataforma.com",
                hashed_password="x",
                role=UserRole.SUPER_ADMIN,
            )
        )
        session.add(
            User(
                id=TENANT_USER_ID,
                tenant_id=TENANT_ID,
                name="Operador",
                email="op@pizzaria.com",
                hashed_password="x",
                role=UserRole.TENANT_USER,
            )
        )
        await session.commit()
    await engine.dispose()  # o TestClient usa outro event loop


asyncio.run(_setup())

client = TestClient(app)
H = {"X-Tenant-ID": str(TENANT_ID)}
H_USER = {**H, "X-User-ID": str(TENANT_USER_ID)}
H_ADMIN = {"X-User-ID": str(SUPER_ADMIN_ID)}

PASS = 0
FAIL = 0


def check(label: str, condition: bool, extra: object = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL += 1
        print(f"FALHA {label} -> {extra}")


def sqlite_exec(sql: str, params: tuple = ()) -> None:
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute(sql, params)
    con.commit()
    con.close()


def webhook(message: str, phone: str = "5511888887777") -> dict:
    r = client.post(
        "/api/v1/webhooks/z-api",
        json={
            "instanceId": "inst-1",
            "phone": phone,
            "fromMe": False,
            "isGroup": False,
            "text": {"message": message},
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def lots_by_batch(ingredient_id: str) -> dict:
    r = client.get(f"/api/v1/ingredients/{ingredient_id}/lots", headers=H)
    assert r.status_code == 200, r.text
    return {lot["batch_number"]: lot for lot in r.json()["lots"]}


today = date.today()

# ---------------------------------------------------------------------------
print("== Setup: ingredientes, lotes e produtos ==")
r = client.post(
    "/api/v1/ingredients",
    json={"name": "Queijo", "unit": "kg", "stock_quantity": "0", "min_stock": "1"},
    headers=H,
)
check("cria ingrediente Queijo", r.status_code == 201, r.text)
queijo_id = r.json()["id"]

for batch, qty, cost, days in (("L1", "2", "10", 3), ("L2", "5", "10", 30)):
    r = client.post(
        f"/api/v1/ingredients/{queijo_id}/lots",
        json={
            "batch_number": batch,
            "supplier_brand": f"Fornecedor {batch}",
            "unit_cost": cost,
            "quantity": qty,
            "expiration_date": (today + timedelta(days=days)).isoformat(),
        },
        headers=H,
    )
    check(f"cria lote {batch}", r.status_code == 201, r.text)

r = client.post(
    "/api/v1/ingredients",
    json={"name": "Leite", "unit": "l", "stock_quantity": "0", "min_stock": "0"},
    headers=H,
)
check("cria ingrediente Leite", r.status_code == 201, r.text)
leite_id = r.json()["id"]
r = client.post(
    f"/api/v1/ingredients/{leite_id}/lots",
    json={
        "batch_number": "LT1",
        "supplier_brand": "Laticinios",
        "unit_cost": "2.50",
        "quantity": "3",
        "expiration_date": (today + timedelta(days=5)).isoformat(),
    },
    headers=H,
)
check("cria lote LT1 (a vencer)", r.status_code == 201, r.text)

r = client.post("/api/v1/products", json={"name": "Pizza", "price": "50"}, headers=H)
check("cria produto Pizza", r.status_code == 201, r.text)
pizza_id = r.json()["id"]
r = client.put(
    f"/api/v1/products/{pizza_id}/recipe",
    json={"items": [{"ingredient_id": queijo_id, "quantity": "1"}]},
    headers=H,
)
check("ficha tecnica Pizza = 1kg Queijo", r.status_code == 200, r.text)

r = client.post("/api/v1/products", json={"name": "Suco", "price": "10"}, headers=H)
check("cria produto Suco", r.status_code == 201, r.text)
suco_id = r.json()["id"]
r = client.put(
    f"/api/v1/products/{suco_id}/recipe",
    json={"items": [{"ingredient_id": leite_id, "quantity": "0.5"}]},
    headers=H,
)
check("ficha tecnica Suco = 0.5l Leite", r.status_code == 200, r.text)

# ---------------------------------------------------------------------------
print("== Venda FEFO via webhook ==")
result = webhook("3x Pizza\n1x Hamburguer")
check("venda processada", result.get("status") == "processed", result)
check("item nao reconhecido reportado", result.get("unmatched") == ["Hamburguer"], result)
lots = lots_by_batch(queijo_id)
check("FEFO: L1 (vence antes) zerado", float(lots["L1"]["current_quantity"]) == 0, lots["L1"])
check("FEFO: L2 baixou so o restante (5-1=4)", float(lots["L2"]["current_quantity"]) == 4, lots["L2"])

# Lote vencido nao e consumido em venda
sqlite_exec(
    "UPDATE ingredient_lots SET expiration_date = ? WHERE batch_number = 'L1'",
    ((today - timedelta(days=1)).isoformat(),),
)
sqlite_exec(
    "UPDATE ingredient_lots SET current_quantity = 10, initial_quantity = 10 "
    "WHERE batch_number = 'L1'",
)
result = webhook("2x Pizza")
check("venda com lote vencido presente processa", result.get("status") == "processed", result)
lots = lots_by_batch(queijo_id)
check("lote vencido L1 intocado", float(lots["L1"]["current_quantity"]) == 10, lots["L1"])
check("L2 consumido no lugar (4-2=2)", float(lots["L2"]["current_quantity"]) == 2, lots["L2"])

# Estoque insuficiente: atomicidade (nada baixa)
result = webhook("50x Pizza")
check("50 pizzas -> failed", result.get("status") == "failed", result)
check(
    "shortage menciona Queijo",
    any("Queijo" in s for s in result.get("details", [])),
    result,
)
lots = lots_by_batch(queijo_id)
check("rollback: L2 segue com 2", float(lots["L2"]["current_quantity"]) == 2, lots["L2"])

# Alerta de estoque baixo: saldo total (12 = 2 nao vencidos + 10 vencidos)
# menos 1 fica <= min_stock 11
r = client.patch(f"/api/v1/ingredients/{queijo_id}", json={"min_stock": "11"}, headers=H)
check("PATCH min_stock -> 200", r.status_code == 200, r.text)
check("PATCH reflete min_stock novo", float(r.json()["min_stock"]) == 11, r.json())
result = webhook("1x Pizza")
check("venda dispara alerta de estoque baixo", result.get("low_stock_alert") is True, result)

# ---------------------------------------------------------------------------
print("== Alertas de vencimento ==")
r = client.get("/api/v1/inventory/expiration-alerts?days=7", headers=H)
check("alertas 200", r.status_code == 200, r.text)
alerts = r.json()
expired_batches = {"vencido": [i for i in alerts["expired"]]}
check(
    "L1 aparece como vencido",
    any(i["status"] == "vencido" and i["ingredient_name"] == "Queijo" for i in alerts["expired"]),
    alerts["expired"],
)
check(
    "LT1 (Leite) aparece como a vencer",
    any(i["status"] == "a_vencer" and i["ingredient_name"] == "Leite" for i in alerts["expiring_soon"]),
    alerts["expiring_soon"],
)
check(
    "dias ate vencer coerentes (vencido negativo)",
    all(i["days_to_expiration"] < 0 for i in alerts["expired"])
    and all(i["days_to_expiration"] >= 0 for i in alerts["expiring_soon"]),
    alerts,
)
# L1: 10kg x R$10 = 100.00 ; LT1: 3l x R$2.50 = 7.50
check(
    "valor em risco = 107.50",
    float(alerts["total_value_at_risk"]) == 107.50,
    alerts["total_value_at_risk"],
)

# ---------------------------------------------------------------------------
print("== Soft delete de ingrediente ==")
r = client.post(
    "/api/v1/ingredients",
    json={"name": "Tomate", "unit": "kg", "stock_quantity": "5", "min_stock": "0"},
    headers=H,
)
tomate_id = r.json()["id"]
r = client.request(
    "DELETE", f"/api/v1/ingredients/{tomate_id}", json={"reason": "abc"}, headers=H_USER
)
check("justificativa curta rejeitada (422)", r.status_code == 422, r.status_code)
r = client.request(
    "DELETE",
    f"/api/v1/ingredients/{tomate_id}",
    json={"reason": "cadastro duplicado"},
    headers=H_USER,
)
check("exclusao com justificativa -> 204", r.status_code == 204, r.text)
r = client.get("/api/v1/ingredients", headers=H)
names = [i["name"] for i in r.json()]
check("listagem nao mostra excluido", "Tomate" not in names, names)
r = client.get(f"/api/v1/ingredients/{tomate_id}", headers=H)
check("GET do excluido -> 404", r.status_code == 404, r.status_code)

r = client.get(f"/api/v1/admin/tenants/{TENANT_ID}/deleted-ingredients", headers=H_ADMIN)
check("admin lista excluidos", r.status_code == 200, r.text)
deleted = r.json()
tomate_row = next((d for d in deleted if d["name"] == "Tomate"), None)
check("excluido aparece no painel admin", tomate_row is not None, deleted)
check(
    "justificativa e autor registrados",
    tomate_row is not None
    and tomate_row["deletion_reason"] == "cadastro duplicado"
    and tomate_row["deleted_by"] is not None
    and tomate_row["deleted_by"]["email"] == "op@pizzaria.com",
    tomate_row,
)

# RBAC do painel admin
r = client.get(f"/api/v1/admin/tenants/{TENANT_ID}/deleted-ingredients")
check("admin sem X-User-ID -> 401", r.status_code == 401, r.status_code)
r = client.get(
    f"/api/v1/admin/tenants/{TENANT_ID}/deleted-ingredients",
    headers={"X-User-ID": str(TENANT_USER_ID)},
)
check("admin com usuario comum -> 403", r.status_code == 403, r.status_code)

r = client.post(f"/api/v1/admin/ingredients/{tomate_id}/restore", headers=H_ADMIN)
check("restore -> 200", r.status_code == 200, r.text)
check("restore devolve estoque total", float(r.json()["total_quantity"]) == 5, r.json())
r = client.get("/api/v1/ingredients", headers=H)
check("restaurado volta a listagem", "Tomate" in [i["name"] for i in r.json()], r.json())

# Venda bloqueada com ingrediente excluido + volta apos restore
r = client.request(
    "DELETE",
    f"/api/v1/ingredients/{leite_id}",
    json={"reason": "teste exclusao em venda"},
    headers=H_USER,
)
check("exclui Leite", r.status_code == 204, r.text)
result = webhook("1x Suco")
check("venda com ingrediente excluido falha", result.get("status") == "failed", result)
check(
    "motivo: ingrediente excluido",
    any("exclu" in s for s in result.get("details", [])),
    result,
)
r = client.post(f"/api/v1/admin/ingredients/{leite_id}/restore", headers=H_ADMIN)
check("restaura Leite", r.status_code == 200, r.text)
result = webhook("1x Suco")
check("apos restore a venda volta a funcionar", result.get("status") == "processed", result)

# ---------------------------------------------------------------------------
print("== Exclusao de produto ==")
r = client.request(
    "DELETE",
    f"/api/v1/products/{suco_id}",
    json={"reason": "saiu do cardapio"},
    headers=H_USER,
)
check("DELETE produto -> 204", r.status_code == 204, r.text)
r = client.get("/api/v1/products", headers=H)
check("produto some da listagem", "Suco" not in [p["name"] for p in r.json()], r.json())
result = webhook("1x Suco")
check(
    "webhook nao reconhece produto excluido",
    result.get("status") == "ignored",
    result,
)

print()
print(f"RESULTADO: {PASS} ok, {FAIL} falha(s)")
sys.exit(1 if FAIL else 0)
