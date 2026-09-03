"""Schemas compartilhados entre recursos."""
from pydantic import BaseModel, Field


class SoftDeleteRequest(BaseModel):
    """Corpo obrigatório do DELETE: nada é excluído sem justificativa."""

    reason: str = Field(
        min_length=5,
        max_length=500,
        description="Justificativa da exclusão (mínimo 5 caracteres)",
    )
