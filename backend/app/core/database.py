"""Engine assíncrona, fábrica de sessões e Base declarativa do SQLAlchemy 2.0."""
from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Convenção de nomes para constraints — essencial para migrações Alembic previsíveis
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# echo=True em desenvolvimento ajuda a depurar o SQL gerado
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependência do FastAPI: entrega uma sessão por requisição.

    O commit é responsabilidade de cada rota/serviço; aqui garantimos
    apenas o fechamento correto da sessão.
    """
    async with AsyncSessionLocal() as session:
        yield session
