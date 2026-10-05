import asyncio
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app import cache
from app.config import redis_settings
from app.main import app
from app.models.message_model import Author, MessageModel
from app.routers import live_chat

client = TestClient(app)

KEY = "live-chat:stream:1:last"
# in the past: a message sent by the chat during the test comes after them
START = datetime(2026, 1, 1, 20, 0, tzinfo=UTC)


def make_messages(count, stream_id=1):
    author = Author(id=1, username="author")
    return [
        MessageModel(
            stream_id=stream_id,
            author=author,
            content=f"message {i}",
            sent_at=START + timedelta(seconds=i),
        )
        for i in range(count)
    ]


@pytest.fixture
def database(monkeypatch):
    # Fake database for the history: keeps the reads, the messages are set by the test
    db = {"messages": [], "reads": []}

    async def fake_get(stream_id, limit):
        db["reads"].append((stream_id, limit))
        return [m for m in db["messages"] if m.stream_id == stream_id][-limit:]

    monkeypatch.setattr(live_chat, "get_last_messages", fake_get)
    return db


@pytest.fixture
def redis(redis_server):
    # Synchronous client on the same fake server, to look at what the service stored
    return fakeredis.FakeRedis(server=redis_server)


def contents(response):
    return [m["content"] for m in response.json()]


def test_history_fills_the_cache_then_reads_it(database, redis):
    database["messages"] = make_messages(3)

    first = client.get("/streams/1/messages")
    second = client.get("/streams/1/messages")

    assert contents(first) == contents(second) == ["message 0", "message 1", "message 2"]
    # only the first request read the database
    assert database["reads"] == [(1, 100)]
    assert redis.llen(KEY) == 3
    assert 0 < redis.ttl(KEY) <= redis_settings.cache_ttl_seconds


def test_cache_keeps_the_last_100_messages(database, redis):
    database["messages"] = make_messages(150)

    response = client.get("/streams/1/messages?limit=100")

    assert contents(response) == [f"message {i}" for i in range(50, 150)]
    assert redis.llen(KEY) == 100


def test_limit_applies_to_the_cached_messages(database):
    database["messages"] = make_messages(60)
    client.get("/streams/1/messages")

    assert contents(client.get("/streams/1/messages")) == [f"message {i}" for i in range(10, 60)]
    assert contents(client.get("/streams/1/messages?limit=2")) == ["message 58", "message 59"]
    assert len(database["reads"]) == 1


def test_each_live_has_its_own_cache(database, redis):
    database["messages"] = make_messages(2, stream_id=1) + make_messages(1, stream_id=2)

    client.get("/streams/1/messages")
    client.get("/streams/2/messages")

    assert redis.llen("live-chat:stream:1:last") == 2
    assert redis.llen("live-chat:stream:2:last") == 1


def test_live_without_messages_is_not_cached(database, redis):
    assert client.get("/streams/1/messages").json() == []
    assert not redis.exists(KEY)


def test_new_message_updates_the_cache(database, saved_messages):
    database["messages"] = make_messages(2)
    client.get("/streams/1/messages")

    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author:
        author.send_json({"content": "new"})
        author.receive_json()

    assert contents(client.get("/streams/1/messages")) == ["message 0", "message 1", "new"]
    # read from the cache, not from the database
    assert len(database["reads"]) == 1


def test_new_message_keeps_the_cache_at_100(database, saved_messages, redis):
    database["messages"] = make_messages(100)
    client.get("/streams/1/messages")

    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author:
        author.send_json({"content": "new"})
        author.receive_json()

    assert redis.llen(KEY) == 100
    assert contents(client.get("/streams/1/messages?limit=1")) == ["new"]


def test_new_message_does_not_create_the_cache(saved_messages, redis):
    # a cache made only of the new messages would hide the older ones in the database
    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author:
        author.send_json({"content": "new"})
        author.receive_json()

    assert not redis.exists(KEY)


def test_message_saved_while_filling_is_not_duplicated(database, redis):
    database["messages"] = make_messages(2)
    client.get("/streams/1/messages")
    # the same message added by the fill and by the chat
    redis.rpush(KEY, database["messages"][1].model_dump_json())

    assert contents(client.get("/streams/1/messages")) == ["message 0", "message 1"]


def test_fill_does_not_replace_an_existing_cache(redis):
    # two viewers missed the cache together: the second fill comes after the first one
    # received a new message, its older read must not erase it
    messages = make_messages(3)
    asyncio.run(cache.fill(1, messages[:3]))
    asyncio.run(cache.fill(1, messages[:2]))

    assert redis.llen(KEY) == 3
    # the aside list of the second fill is not left in Redis
    assert redis.keys() == [KEY.encode()]


def test_invalid_cache_entry_falls_back_to_the_database(database, redis):
    database["messages"] = make_messages(2)
    redis.rpush(KEY, "not json")

    assert contents(client.get("/streams/1/messages")) == ["message 0", "message 1"]
    assert database["reads"] == [(1, 100)]


def test_redis_down_history_reads_the_database(database, redis_server, caplog):
    database["messages"] = make_messages(2)
    redis_server.connected = False

    response = client.get("/streams/1/messages")

    assert response.status_code == 200
    assert contents(response) == ["message 0", "message 1"]
    assert "Chat cache of stream 1 not read" in caplog.text
    assert "Chat cache of stream 1 not filled" in caplog.text


def test_redis_down_chat_still_works(saved_messages, redis_server, caplog):
    redis_server.connected = False

    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author:
        author.send_json({"content": "hello"})
        assert author.receive_json()["content"] == "hello"

    assert [m.content for m in saved_messages] == ["hello"]
    assert f"Message {saved_messages[0].id} not added to the chat cache" in caplog.text
