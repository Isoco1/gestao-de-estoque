"""Agregador de rotas da versão 1 da API."""
from fastapi import APIRouter

from app.api.v1 import ingredients, integrations, inventory, products, webhooks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ingredients.router)
api_router.include_router(products.router)
api_router.include_router(inventory.router)
api_router.include_router(integrations.router)
api_router.include_router(webhooks.router)
