import os
from collections import OrderedDict

# CI has no .env; nothing connects to it since tests replace save_message
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg_async://postgres:postgres@localhost:5432/microservices")

from unittest.mock import AsyncMock

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import cache, events, main
from app.connection_manager import connectionManager
from app.routers import live_chat


@pytest.fixture(autouse=True)
def reset_rate_limit(monkeypatch):
    # connectionManager is a singleton: without this, the last message of a
    # test would rate limit the first message of the next one
    monkeypatch.setattr(connectionManager, "last_sent", OrderedDict())


@pytest.fixture(autouse=True)
def mqtt(monkeypatch):
    # Fake MQTT client: no broker is needed, the published events stay on the mock.
    fake = AsyncMock(connected=True)
    monkeypatch.setattr(events, "mqtt", fake)
    return fake


@pytest.fixture(autouse=True)
def redis_server(monkeypatch):
    # In-memory Redis: the tests never touch a real one. connected = False stops it
    server = fakeredis.FakeServer()
    monkeypatch.setattr(cache, "redis", fakeredis.FakeAsyncRedis(server=server))
    return server


@pytest.fixture
def chat_client(monkeypatch):
    # WebSockets of this client share one event loop, like uvicorn. Without it each
    # connection runs on its own loop, and a broadcast to another one can be lost
    monkeypatch.setattr(main, "init_db", AsyncMock())
    with TestClient(main.app) as client:
        yield client


@pytest.fixture
def saved_messages(monkeypatch):
    saved = []

    async def fake_save(message):
        saved.append(message)

    monkeypatch.setattr(live_chat, "save_message", fake_save)
    return saved


@pytest.fixture
def database_down(monkeypatch):
    async def failing_save(message):
        raise OperationalError("INSERT", {}, Exception("connection refused"))

    monkeypatch.setattr(live_chat, "save_message", failing_save)
