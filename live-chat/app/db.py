from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import CreateSchema

from app.config import db_settings

SCHEMA = "live_chat"

engine = create_async_engine(db_settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


_schema_ready = False


async def init_db() -> None:
    """Creates the schema then the tables, once per process (create_all doesn't create schemas)."""
    global _schema_ready
    if _schema_ready:
        return
    async with engine.begin() as conn:
        await conn.execute(CreateSchema(SCHEMA, if_not_exists=True))
        await conn.run_sync(Base.metadata.create_all)
    _schema_ready = True
