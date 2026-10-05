from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings, settings

SCHEMA_NAME = "search"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA_NAME)


def create_engine_from_settings(app_settings: Settings) -> AsyncEngine:
    return create_async_engine(app_settings.database_url)


async def init_db(engine: AsyncEngine) -> None:
    # Enregistre les tables dans Base.metadata, même si rien d'autre n'a importé les modèles.

    async with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            await connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await connection.run_sync(Base.metadata.create_all)


engine = create_engine_from_settings(settings)
session_factory = async_sessionmaker(engine, expire_on_commit=False)
