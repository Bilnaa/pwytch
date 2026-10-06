import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.cache import get_redis
from app.database import get_session
from app.main import app
from app.models import SCHEMA_NAME, Base


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def engine():
    test_engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool
    ).execution_options(schema_translate_map={SCHEMA_NAME: None})

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def session(engine):
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def fake_redis():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield redis
    await redis.aclose()


@pytest.fixture
async def client(session, fake_redis):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
