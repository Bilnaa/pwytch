import os
from collections import OrderedDict

# CI has no .env; nothing connects to it since tests replace save_message
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg_async://postgres:postgres@localhost:5432/microservices")

import pytest
from sqlalchemy.exc import OperationalError

from app.connection_manager import connectionManager
from app.routers import live_chat


@pytest.fixture(autouse=True)
def reset_rate_limit(monkeypatch):
    # connectionManager is a singleton: without this, the last message of a
    # test would rate limit the first message of the next one
    monkeypatch.setattr(connectionManager, "last_sent", OrderedDict())


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
