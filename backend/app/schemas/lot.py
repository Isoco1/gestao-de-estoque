"""Schemas Pydantic v2 para Lotes de Ingredientes e Alertas de Vencimento."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ingredient import IngredientRead


class LotCreate(BaseModel):
    """Payload de entrada de um novo lote (mercadoria recebida)."""

    batch_number: str | None = Field(default=None, max_length=60)
    supplier_brand: str = Field(min_length=1, max_length=120)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, description="Preço pago por kg/l/un")
    quantity: Decimal = Field(gt=0, description="Quantidade recebida, na unidade do ingrediente")
    manufacturing_date: date | None = Field(default=None, description="Data de fabricação")
    expiration_date: date | None = Field(default=None, description="Nulo se não for perecível")

    @model_validator(mode="after")
    def _validate_dates(self) -> "LotCreate":
        """Coerência entre as datas informadas pelo fabricante."""
        if (
            self.manufacturing_date
            and self.expiration_date
            and self.expiration_date <= self.manufacturing_date
        ):
            raise ValueError("A data de validade deve ser posterior à data de fabricação")
        return self


class LotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_number: str | None
    supplier_brand: str
    unit_cost: Decimal
    initial_quantity: Decimal
    current_quantity: Decimal
    manufacturing_date: date | None
    expiration_date: date | None
    created_at: datetime


class IngredientLotsRead(BaseModel):
    """Resposta da 'janela de detalhes': ingrediente + lotes + métricas."""

    ingredient: IngredientRead
    # Todos os lotes (ativos e zerados), validade mais próxima primeiro
    lots: list[LotRead]
    # Métricas consolidadas
    total_quantity: Decimal
    weighted_average_cost: Decimal | None = Field(
        description="Custo médio ponderado pelos saldos dos lotes ativos; nulo sem estoque"
    )


class ExpirationAlertItem(BaseModel):
    """Um lote perecível vencido ou próximo do vencimento."""

    lot_id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    supplier_brand: str
    batch_number: str | None
    expiration_date: date
    # Dias até vencer (negativo = já vencido há N dias)
    days_to_expiration: int
    status: Literal["vencido", "a_vencer"]
    # Quantidade parada no lote e valor financeiro em risco (qtd x custo unitário)
    quantity: Decimal
    unit_cost: Decimal
    value_at_risk: Decimal


class ExpirationAlertsRead(BaseModel):
    """Resposta consolidada dos alertas de vencimento para o dashboard."""

    reference_date: date
    days_window: int
    expired: list[ExpirationAlertItem]
    expiring_soon: list[ExpirationAlertItem]
    total_value_at_risk: Decimal
