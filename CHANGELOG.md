# Changelog

Histórico de versões do Gestão de Estoque. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/) e
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.3.0] - 2026-08-05

### Segurança e controle de acesso
- **Status de assinatura do tenant** (`ACTIVE` / `PAST_DUE` / `BLOCKED`):
  tenant bloqueado recebe `403 "Assinatura suspensa..."` em toda rota
  protegida, e o webhook do WhatsApp ignora vendas de tenants bloqueados.
  `PAST_DUE` mantém o acesso (período de carência).
- **RBAC — papéis de usuário**: `SUPER_ADMIN` (plataforma, acesso global),
  `TENANT_ADMIN` (dono do negócio) e `TENANT_USER` (operacional), com
  dependências FastAPI prontas para o login JWT futuro.

### Soft delete com auditoria
- **Exclusão de ingredientes exige justificativa** (mínimo 5 caracteres) —
  sem ela a API responde `422`. Nenhum `DELETE` físico é executado: a
  exclusão preenche `deleted_at`, `deleted_by_id` e `deletion_reason`.
- Campos de soft delete também em `Product` e `IngredientLot`.
- **Tabela `AuditLog`**: registro imutável de quem fez o quê, em qual
  recurso e por quê (`DELETE_INGREDIENT`, `RESTORE_INGREDIENT`, ...).
- Todas as listagens ignoram itens excluídos (`WHERE deleted_at IS NULL`)
  e vendas com ingrediente excluído na ficha técnica são recusadas.
- **Painel SUPER_ADMIN**:
  `GET /api/v1/admin/tenants/{id}/deleted-ingredients` (quem deletou,
  quando e a justificativa) e
  `POST /api/v1/admin/ingredients/{id}/restore` (restauração auditada).

### Migração
- Revisão Alembic `dcd771f1e2a1` (enums novos, colunas de soft delete,
  tabela audit_logs, conversão de `users.role` para enum).

## [0.2.0] - 2026-07-24

### Controle de estoque por lotes (FEFO)
- Novo modelo `IngredientLot`: código do lote, fornecedor/marca, custo
  unitário, quantidades inicial/atual, datas de fabricação e validade.
- O estoque do ingrediente passou a ser a **soma dos lotes ativos**;
  baixa de vendas segue **FEFO** (vence antes, sai antes), atravessando
  lotes e ignorando vencidos (perdas/descartes podem consumi-los).
- Rastreabilidade: cada `StockMovement` registra o lote afetado.

### Dashboard e integrações
- `GET /api/v1/inventory/expiration-alerts`: lotes vencidos e a vencer,
  com quantidade parada e valor financeiro em risco (R$).
- `GET /api/v1/integrations/z-api/status`: saúde da conexão WhatsApp com
  degradação limpa (nunca 5xx).
- Janela "Detalhes" do ingrediente no painel: entrada de novos lotes e
  listagem completa dos lotes com status.

### Migrações
- `c9e4b90a1ac1` (esquema inicial com lotes) e `930fae821004`
  (data de fabricação).

## [0.1.0] - 2026-07-23

### MVP inicial
- Arquitetura multi-tenant (todas as tabelas com `tenant_id`).
- Modelos: Tenant, User, Ingredient, Product, ProductRecipe (ficha
  técnica/BOM), StockMovement, Order/OrderItem.
- Webhook Z-API (`POST /api/v1/webhooks/z-api`): interpreta pedidos do
  WhatsApp e executa a baixa de estoque em transação atômica (ACID).
- Alertas de estoque baixo enviados ao WhatsApp do gerente.
- CRUD de ingredientes, produtos e ficha técnica.
- Painel Next.js: Dashboard, Ingredientes e Fichas Técnicas.
- Docker Compose (PostgreSQL), seed de demonstração e `iniciar.bat`.
