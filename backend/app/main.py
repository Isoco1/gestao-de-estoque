"""Ponto de entrada da aplicação FastAPI.

Executar em desenvolvimento:
    uvicorn app.main:app --reload --port 8000
"""
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.zapi_client import close_http_client

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida da aplicação: fecha o cliente HTTP compartilhado (Z-API)."""
    yield
    await close_http_client()


app = FastAPI(
    title="Gestão de Estoque",
    description="Gestão de estoque multi-tenant para restaurantes, deliveries e mercados "
    "com baixa automática via WhatsApp (Z-API).",
    version="0.4.0",
    lifespan=lifespan,
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
