"""Schemas Pydantic v2 para Ingredientes."""
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.ingredient import MeasureUnit


class IngredientBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    unit: MeasureUnit
    min_stock: Decimal = Field(default=Decimal("0"), ge=0)
    cost_per_unit: Decimal | None = Field(default=None, ge=0)


class IngredientCreate(IngredientBase):
    # Quantidade inicial: se > 0, vira automaticamente o primeiro lote
    # (fornecedor "Estoque inicial"), mantendo a rastreabilidade por lotes.
    stock_quantity: Decimal = Field(default=Decimal("0"), ge=0)


class IngredientUpdate(BaseModel):
    """Atualização parcial: todos os campos opcionais."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: MeasureUnit | None = None
    min_stock: Decimal | None = Field(default=None, ge=0)
    cost_per_unit: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class IngredientRead(IngredientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Propriedade calculada no modelo: soma dos lotes com saldo
    total_quantity: Decimal
    is_active: bool


class IngredientDelete(BaseModel):
    """Corpo obrigatório do DELETE: nenhum ingrediente sai sem justificativa."""

    reason: str = Field(
        min_length=5,
        max_length=500,
        description="Justificativa da exclusão (mínimo 5 caracteres)",
    )


class StockEntryCreate(BaseModel):
    """Lançamento manual simples.

    Positiva: entrada avulsa (vira um lote sem validade/fornecedor).
    Negativa: perda/ajuste — baixa FEFO nos lotes (incluindo vencidos,
    para permitir registrar descarte).
    """

    quantity: Decimal = Field(description="Positiva para entrada, negativa para perda/ajuste")
    note: str | None = Field(default=None, max_length=120)
