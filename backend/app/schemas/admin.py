"""Schemas Pydantic v2 do painel administrativo (SUPER_ADMIN)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.ingredient import MeasureUnit


class DeletedByRead(BaseModel):
    """Identificação de quem executou a exclusão."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str


class DeletedIngredientRead(BaseModel):
    """Ingrediente excluído: quem deletou, quando e a justificativa."""

    id: uuid.UUID
    name: str
    unit: MeasureUnit
    deleted_at: datetime
    deletion_reason: str | None
    deleted_by: DeletedByRead | None
