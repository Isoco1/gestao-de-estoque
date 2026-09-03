# Gestão de Estoque 🍕📦

**Versão atual: 0.3.0** — histórico completo em [CHANGELOG.md](CHANGELOG.md)

SaaS multi-tenant de gestão de estoque para pequenos restaurantes, deliveries e
mercados, com **baixa automática de estoque via WhatsApp (Z-API)**.

O estoque é controlado **por lotes** (validade, fornecedor e custo por lote):
o saldo de um ingrediente é a soma dos seus lotes ativos, e as baixas seguem
**FEFO** (*First Expired, First Out* — consome primeiro o lote que vence antes).

## Funcionalidades

- ✅ **Multi-tenant** com isolamento por `tenant_id` em todas as tabelas
- ✅ **Baixa automática via WhatsApp**: webhook Z-API interpreta o pedido e
  desconta a ficha técnica do estoque em transação atômica (ACID)
- ✅ **Controle por lotes com FEFO**: validade, fabricação, fornecedor e
  custo por lote; vendas nunca consomem lote vencido
- ✅ **Alertas**: estoque baixo (WhatsApp do gerente) e vencimentos com
  R$ em risco no dashboard
- ✅ **Status da conexão Z-API** no dashboard (nunca derruba a aplicação)
- ✅ **Bloqueio de inadimplentes** (v0.3): tenant `BLOCKED` recebe 403 em
  toda a API; `PAST_DUE` mantém acesso em carência
- ✅ **RBAC** (v0.3): papéis `SUPER_ADMIN`, `TENANT_ADMIN` e `TENANT_USER`
- ✅ **Soft delete com auditoria** (v0.3): exclusão de ingrediente exige
  justificativa (mínimo 5 caracteres), nunca apaga fisicamente, registra
  quem/quando/por quê em `AuditLog` e é restaurável pelo painel admin

## Stack

| Camada    | Tecnologia                                                    |
|-----------|---------------------------------------------------------------|
| Backend   | Python 3.11+, FastAPI (async), SQLAlchemy 2.0, Alembic        |
| Banco     | PostgreSQL 16                                                 |
| Frontend  | Next.js 14 (App Router), TypeScript, Tailwind CSS, Shadcn/UI  |
| WhatsApp  | Z-API (webhooks de entrada + envio de mensagens)              |

## Estrutura

```
estoque-saas/
├── docker-compose.yml          # PostgreSQL local
├── backend/
│   ├── app/
│   │   ├── main.py             # Entrada FastAPI
│   │   ├── core/               # Config (.env) e conexão com o banco
│   │   ├── models/             # SQLAlchemy 2.0 (todos com tenant_id)
│   │   │   └── ingredient_lot.py   # Lote: validade, fornecedor, custo
│   │   ├── schemas/            # Pydantic v2
│   │   ├── api/v1/             # Rotas: ingredients (+lots), products,
│   │   │                       #   inventory (alertas), integrations, webhooks
│   │   └── services/           # Regras de negócio:
│   │       ├── stock_service.py    # Baixa FEFO por lotes, atômica (ACID)
│   │       ├── order_parser.py     # Interpreta a mensagem do WhatsApp
│   │       └── zapi_client.py      # Envio de mensagens + status da conexão
│   ├── alembic/                # Migrações
│   └── seed_dev.py             # Dados de demonstração
└── frontend/
    ├── app/                    # Páginas: Dashboard, Ingredientes, Fichas Técnicas
    ├── components/ui/          # Componentes estilo Shadcn/UI
    └── lib/api.ts              # Cliente HTTP (injeta X-Tenant-ID)
```

## Como rodar

### Opção rápida (Windows)

Com o Docker Desktop aberto, dê dois cliques em `iniciar.bat` (ou rode no terminal).
Ele sobe o PostgreSQL, prepara o backend, cria os dados de demonstração,
configura o `frontend/.env.local` com o Tenant ID automaticamente e abre a API
e o painel em janelas separadas.

### Manual

### 1. Banco de dados

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate           # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # ajuste se necessário

# Migrações (aplica as revisões versionadas em backend/alembic/versions)
alembic upgrade head

# Dados de demonstração (imprime o Tenant ID)
python seed_dev.py

# Sobe a API
uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local   # cole o Tenant ID impresso pelo seed
npm run dev
```

Painel: http://localhost:3000

## Multi-tenancy

- Toda tabela de dados possui `tenant_id` (FK indexada para `tenants`).
- No MVP, o tenant é identificado pelo header `X-Tenant-ID`; o webhook
  identifica o tenant pelo `instanceId` da Z-API (cada instância = 1 número).
- Próximo passo: autenticação JWT com `tenant_id` na claim, substituindo o
  header sem alterar as rotas (a dependência `get_current_tenant` é o único
  ponto de mudança).

## Fluxo da baixa automática (Z-API)

1. Cliente envia no WhatsApp: `2x Pizza Calabresa`
2. Z-API chama `POST /api/v1/webhooks/z-api`
3. O sistema identifica o tenant pelo `instanceId`, interpreta a mensagem e:
   - busca a ficha técnica de cada produto;
   - calcula a necessidade total de cada ingrediente;
   - **trava os lotes** (`SELECT ... FOR UPDATE`) e valida a disponibilidade
     (lotes **vencidos não contam** — não se vende produto vencido);
   - baixa lote a lote em ordem **FEFO** (vence antes, sai antes), gravando um
     `StockMovement` por fatia consumida com o `lot_id` (rastreabilidade);
   - cria `Order`/`OrderItem` — tudo em **uma transação**; erro = rollback total.
4. Em background: confirma o pedido ao cliente e, se algum ingrediente ficou
   abaixo do mínimo, envia alerta de estoque baixo ao WhatsApp do gerente.

## Lotes, validade e integrações (endpoints principais)

| Endpoint | Função |
|----------|--------|
| `GET /api/v1/ingredients/{id}/lots` | Lotes do ingrediente + estoque total + custo médio ponderado |
| `POST /api/v1/ingredients/{id}/lots` | Entrada de novo lote (fornecedor, custo, validade) |
| `GET /api/v1/inventory/expiration-alerts?days=7` | Lotes vencidos e a vencer, com R$ em risco |
| `GET /api/v1/integrations/z-api/status` | Status da conexão WhatsApp (nunca retorna 5xx) |
| `POST /api/v1/ingredients/{id}/stock-entries` | Entrada avulsa (+) ou perda/descarte FEFO (−, inclui vencidos) |
| `DELETE /api/v1/ingredients/{id}` | Exclusão lógica — corpo `{"reason": "..."}` obrigatório (mín. 5 caracteres) |
| `GET /api/v1/admin/tenants/{id}/deleted-ingredients` | (SUPER_ADMIN) Excluídos do tenant: quem, quando e justificativa |
| `POST /api/v1/admin/ingredients/{id}/restore` | (SUPER_ADMIN) Restaura ingrediente excluído, com auditoria |

## Acesso e segurança (v0.3)

- **Identificação (MVP, pré-JWT)**: `X-Tenant-ID` identifica o tenant e
  `X-User-ID` o usuário (auditoria e rotas `/admin`). O seed imprime os IDs
  de demonstração (SUPER_ADMIN e TENANT_ADMIN).
- **Bloqueio automático**: `Tenant.status = blocked` → toda rota responde
  `403 "Assinatura suspensa. Entre em contato com o suporte..."`, e o
  webhook ignora as vendas. `past_due` mantém o acesso (carência).
- **Regra de ouro do soft delete**: nenhuma exclusão física em tabelas
  críticas; listagens filtram `deleted_at IS NULL` automaticamente e cada
  exclusão/restauração gera um registro imutável em `audit_logs`.

### Testar o webhook sem WhatsApp

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/z-api -H "Content-Type: application/json" -d "{\"instanceId\": \"DEMO_INSTANCE_123\", \"phone\": \"5511988887777\", \"fromMe\": false, \"isGroup\": false, \"text\": {\"message\": \"2x Pizza Calabresa\"}}"
```

## Roadmap (próximas etapas)

- [ ] Autenticação JWT (login por tenant) e RBAC
- [ ] Tela de histórico de movimentações e vendas
- [ ] Janela de detalhes de lotes no painel (a API `GET /ingredients/{id}/lots` já existe)
- [ ] Cadastro/edição de produtos com preço e categorias
- [ ] Parser de pedidos com LLM (mensagens livres) mantendo a interface atual
- [ ] Relatórios de custo (CMV) usando o custo real por lote
- [ ] Onboarding de tenants (cadastro self-service + credenciais Z-API)
