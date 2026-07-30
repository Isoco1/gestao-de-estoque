"""Webhook da Z-API: recebe mensagens do WhatsApp e dispara a baixa de estoque.

Fluxo:
  1. Identifica o tenant pelo instanceId do payload.
  2. Interpreta a mensagem (parser) e extrai itens do pedido.
  3. Executa a baixa em transação atômica (stock_service).
  4. Responde ao cliente e alerta o gerente sobre estoque baixo (Z-API).

Importante: webhooks devem SEMPRE responder 200 rapidamente, senão a
Z-API reenvia a notificação. Erros de negócio são registrados e
reportados no corpo da resposta, nunca como 5xx.
"""
import logging

from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models.order import OrderSource
from app.models.tenant import Tenant
from app.schemas.webhook import ZapiWebhookPayload
from app.services.order_parser import parse_order_message
from app.services.stock_service import InsufficientStockError, process_sale
from app.services.zapi_client import ZapiClient, notify_low_stock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _send_confirmation(tenant: Tenant, phone: str, message: str) -> None:
    """Tarefa em background: responde o cliente sem atrasar o webhook."""
    try:
        await ZapiClient(tenant).send_text(phone, message)
    except ValueError as exc:
        logger.warning("Confirmação não enviada: %s", exc)


@router.post("/z-api")
async def zapi_webhook(
    payload: ZapiWebhookPayload,
    session: SessionDep,
    background_tasks: BackgroundTasks,
):
    # Ignora mensagens enviadas pelo próprio número e mensagens de grupo
    if payload.from_me or payload.is_group:
        return {"status": "ignored", "reason": "mensagem própria ou de grupo"}

    if not payload.instance_id or not payload.message_text.strip():
        return {"status": "ignored", "reason": "payload sem instância ou sem texto"}

    # 1. Identifica o tenant pela instância Z-API
    tenant = (
        await session.execute(
            select(Tenant).where(
                Tenant.zapi_instance_id == payload.instance_id,
                Tenant.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not tenant:
        logger.warning("Webhook de instância desconhecida: %s", payload.instance_id)
        return {"status": "ignored", "reason": "instância não cadastrada"}

    # Desanexa o tenant da sessão: um rollback expira objetos anexados, e o
    # tenant ainda é lido depois (logs e envio de mensagens em background).
    session.expunge(tenant)

    # 2. Interpreta a mensagem
    parsed_items = parse_order_message(payload.message_text)
    if not parsed_items:
        return {"status": "ignored", "reason": "nenhum item identificado na mensagem"}

    # 3. Baixa de estoque em transação atômica
    try:
        result = await process_sale(
            session,
            tenant.id,
            parsed_items,
            source=OrderSource.WHATSAPP,
            customer_phone=payload.phone,
            raw_message=payload.message_text,
        )
        await session.commit()
    except InsufficientStockError as exc:
        await session.rollback()  # nada foi baixado (ACID)
        logger.warning("Estoque insuficiente no tenant %s: %s", tenant.slug, exc.shortages)
        if payload.phone:
            background_tasks.add_task(
                _send_confirmation,
                tenant,
                payload.phone,
                "⚠️ Não foi possível registrar o pedido: estoque insuficiente. "
                "Um atendente entrará em contato.",
            )
        return {"status": "failed", "reason": "estoque insuficiente", "details": exc.shortages}
    except ValueError as exc:
        await session.rollback()
        return {"status": "ignored", "reason": str(exc)}
    except Exception:
        await session.rollback()
        logger.exception("Erro inesperado ao processar webhook do tenant %s", tenant.slug)
        return {"status": "error", "reason": "erro interno; venda não registrada"}

    # 4. Confirmação ao cliente + alerta de estoque baixo ao gerente (async)
    if payload.phone:
        items_text = "\n".join(f"• {qty}x {name}" for name, qty in result.matched_items)
        background_tasks.add_task(
            _send_confirmation,
            tenant,
            payload.phone,
            f"✅ Pedido registrado!\n\n{items_text}",
        )
    if result.low_stock_items:
        background_tasks.add_task(notify_low_stock, tenant, result.low_stock_items)

    return {
        "status": "processed",
        "order_id": str(result.order_id),
        "matched": result.matched_items,
        "unmatched": result.unmatched_names,
        "low_stock_alert": bool(result.low_stock_items),
    }
