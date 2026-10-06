import os

import fakeredis

os.environ.setdefault("DATABASE_URL", "sqlite://")

from unittest.mock import AsyncMock

import pytest
from app.cache import get_redis
from app.database import get_session
from app.dependencies import get_mqtt
from app.main import app
from app.models import Base
from common.mqtt import MqttClient
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestingSession() as session:
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def client(db_session, fake_mqtt, fake_redis):
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_mqtt] = lambda: fake_mqtt
    app.dependency_overrides[get_redis] = lambda: fake_redis


    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def fake_mqtt():
    return AsyncMock(spec=MqttClient)
