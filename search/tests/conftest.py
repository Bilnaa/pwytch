import pytest
from app.infra.db import SCHEMA_NAME, init_db
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    test_engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool
    ).execution_options(schema_translate_map={SCHEMA_NAME: None})
    await init_db(test_engine)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def session(engine):
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
