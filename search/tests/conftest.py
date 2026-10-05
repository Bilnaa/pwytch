from unittest.mock import AsyncMock

import pytest
from common.mqtt import MqttClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db import SCHEMA_NAME, init_db
from app.dependencies import get_mqtt, get_session
from app.main import app


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
def session_factory(engine):
    # Mêmes options que la fabrique de prod dans app.core.db.
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def fake_mqtt():
    return AsyncMock(spec=MqttClient)


@pytest.fixture
async def client(session, fake_mqtt):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_mqtt] = lambda: fake_mqtt
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
