"""Ponto de entrada da aplicação FastAPI.

Executar em desenvolvimento:
    uvicorn app.main:app --reload --port 8000
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Gestão de Estoque",
    description="Gestão de estoque multi-tenant para restaurantes, deliveries e mercados "
    "com baixa automática via WhatsApp (Z-API).",
    version="0.1.0",
)

# CORS: libera o frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["Infra"])
async def health_check():
    """Usado por load balancers e monitoramento."""
    return {"status": "ok"}
