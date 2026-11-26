# Inventory Management 🍕📦

🇧🇷 [Leia em português](README.PT.md)

**Current version: 0.3.0** — full history in [CHANGELOG.md](CHANGELOG.md)

Multi-tenant inventory management SaaS for small restaurants, delivery
businesses and grocery stores, with **automatic stock deduction via WhatsApp (Z-API)**.

Stock is tracked **by lot** (expiration date, supplier and cost per lot):
an ingredient's balance is the sum of its active lots, and deductions follow
**FEFO** (*First Expired, First Out* — the lot that expires first is consumed first).

## Features

- ✅ **Multi-tenant** with `tenant_id` isolation on every table
- ✅ **Automatic deduction via WhatsApp**: a Z-API webhook parses the order and
  deducts the recipe's ingredients from stock in an atomic (ACID) transaction
- ✅ **Lot control with FEFO**: expiration date, manufacturing date, supplier and
  cost per lot; sales never consume an expired lot
- ✅ **Alerts**: low stock (sent to the manager's WhatsApp) and upcoming
  expirations with the amount (R$) at risk on the dashboard
- ✅ **Z-API connection status** on the dashboard (never takes the application down)
- ✅ **Blocking of delinquent accounts** (v0.3): a `BLOCKED` tenant gets 403 on
  the entire API; `PAST_DUE` keeps access during a grace period
- ✅ **RBAC** (v0.3): `SUPER_ADMIN`, `TENANT_ADMIN` and `TENANT_USER` roles
- ✅ **Soft delete with auditing** (v0.3): deleting an ingredient requires a
  justification (at least 5 characters), never deletes physically, records
  who/when/why in `AuditLog` and can be restored from the admin panel

## Stack

| Layer     | Technology                                                    |
|-----------|---------------------------------------------------------------|
| Backend   | Python 3.11+, FastAPI (async), SQLAlchemy 2.0, Alembic        |
| Database  | PostgreSQL 16                                                 |
| Frontend  | Next.js 14 (App Router), TypeScript, Tailwind CSS, Shadcn/UI  |
| WhatsApp  | Z-API (incoming webhooks + message sending)                   |

## Structure

```
estoque-saas/
├── docker-compose.yml          # Local PostgreSQL
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── core/               # Config (.env) and database connection
│   │   ├── models/             # SQLAlchemy 2.0 (all with tenant_id)
│   │   │   └── ingredient_lot.py   # Lot: expiration, supplier, cost
│   │   ├── schemas/            # Pydantic v2
│   │   ├── api/v1/             # Routes: ingredients (+lots), products,
│   │   │                       #   inventory (alerts), integrations, webhooks
│   │   └── services/           # Business rules:
│   │       ├── stock_service.py    # Atomic (ACID) FEFO deduction by lot
│   │       ├── order_parser.py     # Parses the WhatsApp message
│   │       └── zapi_client.py      # Message sending + connection status
│   ├── alembic/                # Migrations
│   └── seed_dev.py             # Demo data
└── frontend/
    ├── app/                    # Pages: Dashboard, Ingredients, Recipes
    ├── components/ui/          # Shadcn/UI-style components
    └── lib/api.ts              # HTTP client (injects X-Tenant-ID)
```

## Getting started

### Quick option (Windows)

With Docker Desktop running, double-click `iniciar.bat` (or run it from the terminal).
It starts PostgreSQL, sets up the backend, creates the demo data,
automatically writes the Tenant ID to `frontend/.env.local`, and opens the API
and the dashboard in separate windows.

### Manual

### 1. Database

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate           # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # adjust if needed

# Migrations (applies the versioned revisions in backend/alembic/versions)
alembic upgrade head

# Demo data (prints the Tenant ID)
python seed_dev.py

# Start the API
uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local   # paste the Tenant ID printed by the seed
npm run dev
```

Dashboard: http://localhost:3000

## Multi-tenancy

- Every data table has a `tenant_id` (indexed FK to `tenants`).
- In the MVP, the tenant is identified by the `X-Tenant-ID` header; the webhook
  identifies the tenant by the Z-API `instanceId` (each instance = 1 phone number).
- Next step: JWT authentication with `tenant_id` in the claim, replacing the
  header without changing the routes (the `get_current_tenant` dependency is the
  only point of change).

## Automatic deduction flow (Z-API)

1. A customer sends on WhatsApp: `2x Pizza Calabresa`
2. Z-API calls `POST /api/v1/webhooks/z-api`
3. The system identifies the tenant by its `instanceId`, parses the message and:
   - looks up the recipe for each product;
   - calculates the total amount needed of each ingredient;
   - **locks the lots** (`SELECT ... FOR UPDATE`) and checks availability
     (**expired lots don't count** — expired products are never sold);
   - deducts lot by lot in **FEFO** order (first to expire, first out), recording a
     `StockMovement` with the `lot_id` for each portion consumed (traceability);
   - creates the `Order`/`OrderItem` — all in **a single transaction**; any error = full rollback.
4. In the background: confirms the order to the customer and, if any ingredient fell
   below its minimum, sends a low-stock alert to the manager's WhatsApp.

## Lots, expiration and integrations (main endpoints)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ingredients/{id}/lots` | Ingredient lots + total stock + weighted average cost |
| `POST /api/v1/ingredients/{id}/lots` | New lot entry (supplier, cost, expiration) |
| `GET /api/v1/inventory/expiration-alerts?days=7` | Expired and soon-to-expire lots, with R$ at risk |
| `GET /api/v1/integrations/z-api/status` | WhatsApp connection status (never returns 5xx) |
| `POST /api/v1/ingredients/{id}/stock-entries` | Ad-hoc entry (+) or FEFO loss/disposal (−, includes expired lots) |
| `DELETE /api/v1/ingredients/{id}` | Soft delete — body `{"reason": "..."}` required (min. 5 characters) |
| `GET /api/v1/admin/tenants/{id}/deleted-ingredients` | (SUPER_ADMIN) Tenant's deleted ingredients: who, when and why |
| `POST /api/v1/admin/ingredients/{id}/restore` | (SUPER_ADMIN) Restores a deleted ingredient, with auditing |

## Access and security (v0.3)

- **Identification (MVP, pre-JWT)**: `X-Tenant-ID` identifies the tenant and
  `X-User-ID` the user (auditing and `/admin` routes). The seed prints the demo
  IDs (SUPER_ADMIN and TENANT_ADMIN).
- **Automatic blocking**: `Tenant.status = blocked` → every route returns
  `403 "Assinatura suspensa. Entre em contato com o suporte..."` (subscription
  suspended), and the webhook ignores sales. `past_due` keeps access (grace period).
- **Golden rule of soft delete**: no physical deletion on critical tables;
  listings automatically filter `deleted_at IS NULL`, and every
  deletion/restoration creates an immutable record in `audit_logs`.

### Testing the webhook without WhatsApp

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/z-api -H "Content-Type: application/json" -d "{\"instanceId\": \"DEMO_INSTANCE_123\", \"phone\": \"5511988887777\", \"fromMe\": false, \"isGroup\": false, \"text\": {\"message\": \"2x Pizza Calabresa\"}}"
```

## Roadmap (next steps)

- [ ] JWT authentication (per-tenant login) and RBAC
- [ ] Stock movement and sales history screen
- [ ] Lot details window in the dashboard (the `GET /ingredients/{id}/lots` API already exists)
- [ ] Product registration/editing with prices and categories
- [ ] LLM-based order parser (free-form messages) keeping the current interface
- [ ] Cost reports (COGS) using the real cost per lot
- [ ] Tenant onboarding (self-service sign-up + Z-API credentials)
