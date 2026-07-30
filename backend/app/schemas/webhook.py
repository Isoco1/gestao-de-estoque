"""Schema do payload de webhook da Z-API.

A Z-API envia diversos campos; mapeamos apenas os necessários e ignoramos
o restante (model_config extra='ignore' é o padrão do Pydantic v2).
Referência: https://developer.z-api.io/webhooks/on-message-received
"""
from pydantic import BaseModel, Field


class ZapiTextContent(BaseModel):
    message: str = ""


class ZapiWebhookPayload(BaseModel):
    instance_id: str | None = Field(default=None, alias="instanceId")
    phone: str | None = None
    sender_name: str | None = Field(default=None, alias="senderName")
    from_me: bool = Field(default=False, alias="fromMe")
    is_group: bool = Field(default=False, alias="isGroup")
    text: ZapiTextContent | None = None

    @property
    def message_text(self) -> str:
        return self.text.message if self.text else ""
