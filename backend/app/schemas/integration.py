"""Schemas Pydantic v2 para integrações externas (Z-API)."""
from pydantic import BaseModel


class ZapiStatusRead(BaseModel):
    """Payload limpo do status da conexão WhatsApp para o dashboard."""

    connected: bool
    phone_number: str | None = None
    # Ex: "CONNECTED", "DISCONNECTED", "CREDENCIAIS_NAO_CONFIGURADAS", "ZAPI_INACESSIVEL"
    status_message: str
