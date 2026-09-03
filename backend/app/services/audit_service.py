"""Registro centralizado de auditoria para ações sensíveis (DRY).

Toda exclusão/restauração passa por aqui — nunca crie AuditLog direto
nas rotas, para manter o formato dos registros consistente.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


def log_action(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    user: User | None,
    action: str,
    resource_name: str,
    resource_id: uuid.UUID | str,
    reason: str | None = None,
) -> AuditLog:
    """Adiciona um registro de auditoria à sessão (commit é do chamador,
    garantindo que o log entra na MESMA transação da ação auditada)."""
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user.id if user else None,
        action=action,
        resource_name=resource_name,
        resource_id=str(resource_id),
        reason=reason,
    )
    session.add(entry)
    return entry
