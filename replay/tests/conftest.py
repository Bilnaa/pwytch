import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infra.db import get_session, init_db
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    test_engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    await init_db(test_engine)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def session(engine):
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session


@pytest.fixture
def session_factory(engine):
    # Mêmes options que la fabrique de prod dans app.infra.db.
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    # ASGITransport ne lance pas le lifespan : ni Postgres ni broker.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
