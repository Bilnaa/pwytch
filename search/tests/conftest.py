import pytest
from app.infra.db import SCHEMA_NAME, get_session, init_db
from app.main import app
from httpx import ASGITransport, AsyncClient
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


@pytest.fixture
async def client(session):
    # The route reads the same in-memory database the test fills through the handlers.
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    # ASGITransport does not run the lifespan: the MQTT consumer stays off in tests.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
