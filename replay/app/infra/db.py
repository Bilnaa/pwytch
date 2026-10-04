import logging
from collections.abc import AsyncIterator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.infra.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


async def init_db(engine: AsyncEngine) -> None:
    # Importé ici pour enregistrer les tables dans Base.metadata avant create_all.
    from app.infra import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def try_init_db(engine: AsyncEngine) -> bool:
    """Au démarrage : une base indisponible ne doit pas empêcher le service de démarrer."""
    try:
        await init_db(engine)
    # asyncpg lève un ConnectionRefusedError brut (OSError) quand Postgres est coupé.
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("Database unavailable at startup, tables not created: %s", exc)
        return False
    return True


engine = create_async_engine(settings.database_url)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
