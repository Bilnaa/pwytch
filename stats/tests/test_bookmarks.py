from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from common.events import BookmarkDeleted
from common.topics import BOOKMARK_DELETED

from app import handlers
from app.counters import increment_counter
from app.handlers import on_bookmark_deleted


async def record_deletions(session, deletions: dict[str, int]) -> None:
    for key, times in deletions.items():
        for _ in range(times):
            await increment_counter(session, BOOKMARK_DELETED, key)


@pytest.mark.anyio
async def test_get_bookmark_deleted_stats_return_unprocessable_entity(client):
    response = await client.get("/stats/bookmarks/deleted/chaussette/1")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_get_bookmark_deleted_stats_never_counted_returns_zero(client):
    response = await client.get("/stats/bookmarks/deleted/replay/1")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"target_type": "replay", "target_id": 1, "count": 0}


@pytest.mark.anyio
async def test_get_bookmark_deleted_stats_counted_target(client, session):
    # same key format as the handler: "<target_type>:<target_id>"
    for _ in range(3):
        await increment_counter(session, BOOKMARK_DELETED, "replay:42")

    response = await client.get("/stats/bookmarks/deleted/replay/42")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"target_type": "replay", "target_id": 42, "count": 3}


@pytest.mark.anyio
async def test_get_top_deleted_sorted_by_count_descending(client, session):
    await record_deletions(session, {"replay:1": 1, "replay:2": 3, "replay:3": 2})

    response = await client.get("/stats/bookmarks/deleted/top")

    assert response.status_code == HTTPStatus.OK
    assert [item["target_id"] for item in response.json()] == [2, 3, 1]


@pytest.mark.anyio
async def test_get_top_deleted_breaks_ties_by_key(client, session):
    # inserted in reverse order: only the second sort criterion puts "1" first
    await record_deletions(session, {"replay:2": 2, "replay:1": 2})

    response = await client.get("/stats/bookmarks/deleted/top")

    assert response.status_code == HTTPStatus.OK
    assert [item["target_id"] for item in response.json()] == [1, 2]


@pytest.mark.anyio
async def test_get_top_deleted_filters_by_target_type(client, session):
    await record_deletions(session, {"replay:1": 1, "streamer:1": 5})

    response = await client.get(
        "/stats/bookmarks/deleted/top", params={"target_type": "replay"}
    )

    assert response.status_code == HTTPStatus.OK
    items = response.json()
    assert len(items) == 1
    assert items[0]["target_type"] == "replay"


@pytest.mark.anyio
async def test_get_top_deleted_respects_limit(client, session):
    await record_deletions(session, {"replay:1": 1, "replay:2": 1, "replay:3": 1})

    response = await client.get("/stats/bookmarks/deleted/top", params={"limit": 2})

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2


@pytest.mark.anyio
async def test_get_top_deleted_empty_database(client):
    response = await client.get("/stats/bookmarks/deleted/top")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@pytest.mark.anyio
@pytest.mark.parametrize("limit", [0, 501])
async def test_get_top_deleted_invalid_limit_returns_422(client, limit):
    response = await client.get("/stats/bookmarks/deleted/top", params={"limit": limit})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_on_bookmark_deleted_creates_then_increments_counter(
    client, session_factory, fake_redis, monkeypatch
):
    # the handler opens its own session: point it to the test database
    monkeypatch.setattr(handlers, "SessionLocal", session_factory)
    event = BookmarkDeleted(
        bookmark_id=7,
        target_type="replay",
        target_id=42,
        user_id=1,
        deleted_at=datetime.now(UTC),
    )

    await on_bookmark_deleted(event)
    first_response = await client.get("/stats/bookmarks/deleted/replay/42")

    assert first_response.status_code == HTTPStatus.OK
    assert first_response.json()["count"] == 1

    await on_bookmark_deleted(event)
    await fake_redis.flushall()
    second_response = await client.get("/stats/bookmarks/deleted/replay/42")

    assert second_response.status_code == HTTPStatus.OK
    assert second_response.json()["count"] == 2


@pytest.mark.anyio
async def test_get_bookmark_deleted_stats_non_numeric_target_id_returns_422(client):
    response = await client.get("/stats/bookmarks/deleted/streamer/abc")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY