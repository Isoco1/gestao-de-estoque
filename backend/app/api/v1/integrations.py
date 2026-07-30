"""Status de integrações externas (Z-API / WhatsApp) para o dashboard."""
from fastapi import APIRouter

from app.api.deps import TenantDep
from app.schemas.integration import ZapiStatusRead
from app.services.zapi_client import check_connection

router = APIRouter(prefix="/integrations", tags=["Integrações"])


@router.get("/z-api/status", response_model=ZapiStatusRead)
async def zapi_status(tenant: TenantDep):
    """Verifica a conexão do WhatsApp do tenant na Z-API.

    Nunca retorna 5xx por indisponibilidade da Z-API: cenários de erro
    (credenciais ausentes, token inválido, Z-API fora do ar) degradam
    para `connected: false` com um `status_message` descritivo.
    """
    return await check_connection(tenant)
