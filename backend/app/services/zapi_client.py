"""Cliente HTTP para envio de mensagens via Z-API.

Cada Tenant possui sua própria instância (instance_id + token) armazenada
no banco. O Client-Token global vem das configurações (.env).
Documentação: https://developer.z-api.io/message/send-message-text
"""
import logging

import httpx

from app.core.config import settings
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Cliente HTTP único do processo: reutiliza conexões (keep-alive) entre as
# chamadas em vez de abrir/fechar um cliente por requisição. Fechado no
# lifespan da aplicação (app/main.py).
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10)
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
    _http_client = None


class ZapiClient:
    """Encapsula chamadas à Z-API (Single Responsibility)."""

    def __init__(self, tenant: Tenant) -> None:
        if not tenant.zapi_instance_id or not tenant.zapi_instance_token:
            raise ValueError(f"Tenant {tenant.slug} não possui credenciais Z-API configuradas")
        self._base_url = (
            f"{settings.zapi_base_url}/instances/{tenant.zapi_instance_id}"
            f"/token/{tenant.zapi_instance_token}"
        )
        self._headers = {"Client-Token": settings.zapi_client_token}

    async def get_status(self) -> dict:
        """Consulta o status da instância na Z-API (conexão do WhatsApp).

        Levanta httpx.HTTPError em falha de rede/HTTP — o chamador decide
        como degradar (ver check_connection).
        """
        response = await get_http_client().get(f"{self._base_url}/status", headers=self._headers)
        response.raise_for_status()
        return response.json()

    async def get_device_phone(self) -> str | None:
        """Retorna o número de telefone conectado à instância, se disponível."""
        response = await get_http_client().get(f"{self._base_url}/device", headers=self._headers)
        response.raise_for_status()
        data = response.json()
        phone = data.get("phone")
        return str(phone) if phone else None

    async def send_text(self, phone: str, message: str) -> bool:
        """Envia mensagem de texto. Retorna True em caso de sucesso.

        Falhas de envio NUNCA devem derrubar o fluxo principal (a baixa de
        estoque já foi commitada); por isso capturamos e logamos o erro.
        """
        try:
            response = await get_http_client().post(
                f"{self._base_url}/send-text",
                json={"phone": phone, "message": message},
                headers=self._headers,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("Falha ao enviar mensagem Z-API para %s: %s", phone, exc)
            return False


async def check_connection(tenant: Tenant) -> dict:
    """Verifica a saúde da conexão WhatsApp do tenant, sem nunca levantar erro.

    Retorna o payload limpo consumido pelo dashboard:
        {"connected": bool, "phone_number": str | None, "status_message": str}
    """
    try:
        client = ZapiClient(tenant)
    except ValueError:
        return {
            "connected": False,
            "phone_number": None,
            "status_message": "CREDENCIAIS_NAO_CONFIGURADAS",
        }

    try:
        status = await client.get_status()
    except httpx.HTTPError as exc:
        logger.warning("Z-API inacessível para o tenant %s: %s", tenant.slug, exc)
        return {"connected": False, "phone_number": None, "status_message": "ZAPI_INACESSIVEL"}

    connected = bool(status.get("connected"))
    if not connected:
        # A Z-API descreve o motivo no campo "error" (ex: "You are not connected")
        return {
            "connected": False,
            "phone_number": None,
            "status_message": str(status.get("error") or "DISCONNECTED").upper(),
        }

    # Conectado: tenta enriquecer com o número do aparelho (não é crítico)
    phone_number = None
    try:
        phone_number = await client.get_device_phone()
    except httpx.HTTPError:
        logger.debug("Não foi possível obter o número do aparelho do tenant %s", tenant.slug)

    return {"connected": True, "phone_number": phone_number, "status_message": "CONNECTED"}


async def notify_low_stock(tenant: Tenant, low_stock_items: list[dict]) -> None:
    """Envia alerta de estoque baixo para o WhatsApp do gerente do tenant.

    `low_stock_items`: [{"name": str, "stock": Decimal, "min": Decimal, "unit": str}]
    """
    if not low_stock_items or not tenant.manager_phone:
        return

    lines = [
        f"• {item['name']}: {item['stock']} {item['unit']} (mínimo: {item['min']} {item['unit']})"
        for item in low_stock_items
    ]
    message = "⚠️ *Alerta de Estoque Baixo*\n\nOs itens abaixo atingiram o estoque mínimo:\n" + "\n".join(lines)

    try:
        client = ZapiClient(tenant)
        await client.send_text(tenant.manager_phone, message)
    except ValueError as exc:
        logger.warning("Alerta de estoque não enviado: %s", exc)
