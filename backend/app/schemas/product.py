"""Schemas Pydantic v2 para Produtos e Ficha Técnica."""
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingredient import IngredientRead


class RecipeItemInput(BaseModel):
    """Item da ficha técnica enviado pelo painel."""

    ingredient_id: uuid.UUID
    quantity: Decimal = Field(gt=0, description="Quantidade na unidade do ingrediente")


class RecipeItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity: Decimal
    ingredient: IngredientRead


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price: Decimal = Field(default=Decimal("0"), ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    price: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price: Decimal
    is_active: bool
    recipe_items: list[RecipeItemRead] = []


class RecipeReplaceInput(BaseModel):
    """Substitui a ficha técnica completa do produto (operação idempotente)."""

    items: list[RecipeItemInput]
