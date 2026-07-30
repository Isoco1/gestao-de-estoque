"""Configurações centrais da aplicação, carregadas do arquivo .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variáveis de ambiente tipadas (Pydantic v2)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Banco de dados
    database_url: str = "postgresql+asyncpg://estoque:estoque123@localhost:5432/estoque_saas"

    # Geral
    environment: str = "development"
    frontend_origin: str = "http://localhost:3000"

    # Z-API (fallback global; credenciais por tenant ficam no banco)
    zapi_base_url: str = "https://api.z-api.io"
    zapi_client_token: str = ""


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância única (cache) das configurações."""
    return Settings()


settings = get_settings()
