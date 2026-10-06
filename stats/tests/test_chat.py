from datetime import UTC, datetime
from http import HTTPStatus
from uuid import uuid4

import pytest
from common.events import ChatMessage
from common.topics import CHAT_MESSAGE

from app import handlers
from app.counters import increment_counter
from app.handlers import on_chat_message
from app.utils import LIMIT_INTEGER


async def record_messages(session, messages: dict[str, int]) -> None:
    for key, times in messages.items():
        for _ in range(times):
            await increment_counter(session, CHAT_MESSAGE, key)


@pytest.mark.anyio
@pytest.mark.parametrize("stream_id", ["abc", "0", str(LIMIT_INTEGER + 1)])
async def test_get_chat_stats_invalid_stream_id_returns_422(client, stream_id):
    response = await client.get(f"/stats/chat/{stream_id}")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_get_chat_stats_never_counted_returns_zero(client):
    response = await client.get("/stats/chat/1")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"stream_id": 1, "count": 0}


@pytest.mark.anyio
async def test_get_chat_stats_counted_stream(client, session):
    # same key format as the handler: the stream id as text
    await record_messages(session, {"42": 3})

    response = await client.get("/stats/chat/42")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"stream_id": 42, "count": 3}


@pytest.mark.anyio
async def test_get_top_chat_sorted_by_count_descending(client, session):
    await record_messages(session, {"1": 1, "2": 3, "3": 2})

    response = await client.get("/stats/chat/top")

    assert response.status_code == HTTPStatus.OK
    assert [item["stream_id"] for item in response.json()] == [2, 3, 1]


@pytest.mark.anyio
async def test_get_top_chat_breaks_ties_by_key(client, session):
    # inserted in reverse order: only the second sort criterion puts 1 first
    await record_messages(session, {"2": 2, "1": 2})

    response = await client.get("/stats/chat/top")

    assert response.status_code == HTTPStatus.OK
    assert [item["stream_id"] for item in response.json()] == [1, 2]


@pytest.mark.anyio
async def test_get_top_chat_respects_limit(client, session):
    await record_messages(session, {"1": 1, "2": 1, "3": 1})

    response = await client.get("/stats/chat/top", params={"limit": 2})

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("limit", [0, 501])
async def test_get_top_chat_invalid_limit_returns_422(client, limit):
    response = await client.get("/stats/chat/top", params={"limit": limit})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_get_top_chat_empty_database(client):
    response = await client.get("/stats/chat/top")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


def make_chat_message(stream_id: int) -> ChatMessage:
    return ChatMessage(
        message_id=uuid4(),
        stream_id=stream_id,
        author_id=1,
        author_name="saul goodman",
        content="hello",
        sent_at=datetime.now(UTC),
    )


@pytest.mark.anyio
async def test_on_chat_message_creates_then_increments_counter(
    client, session_factory, fake_redis, monkeypatch
):
    # the handler opens its own session: point it to the test database
    monkeypatch.setattr(handlers, "SessionLocal", session_factory)

    await on_chat_message(make_chat_message(stream_id=42))
    first_response = await client.get("/stats/chat/42")

    assert first_response.status_code == HTTPStatus.OK
    assert first_response.json()["count"] == 1

    await on_chat_message(make_chat_message(stream_id=42))
    await fake_redis.flushall()
    second_response = await client.get("/stats/chat/42")

    assert second_response.status_code == HTTPStatus.OK
    assert second_response.json()["count"] == 2