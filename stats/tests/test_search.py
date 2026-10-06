from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from common.events import SearchHit
from common.topics import SEARCH_HIT

from app import handlers
from app.counters import increment_counter
from app.handlers import on_search_hit


@pytest.mark.anyio
async def test_get_search_stats_return_unprocessable_entity(
    client
):
    item_id = 1
    item_type = "chaussette"
    response = await client.get(
        f"/stats/search/{item_type}/{item_id}",
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_get_search_stats_never_counted_returns_zero(client):
    response = await client.get("/stats/search/streamer/1")
 
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"item_type": "streamer", "item_id": "1", "count": 0}


@pytest.mark.anyio
async def test_get_search_stats_counted_item(client, session):
    # same key format as the handler: "<item_type>:<item_id>"
    for _ in range(3):
        await increment_counter(session, SEARCH_HIT, "streamer:42")

    response = await client.get("/stats/search/streamer/42")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"item_type": "streamer", "item_id": "42", "count": 3}


@pytest.mark.anyio
async def test_get_top_sorted_by_count_descending(client, session):
    hits = {"streamer:1": 1, "streamer:2": 3, "streamer:3": 2}
    for key, times in hits.items():
        for _ in range(times):
            await increment_counter(session, SEARCH_HIT, key)

    response = await client.get("/stats/search/top")

    assert response.status_code == HTTPStatus.OK
    assert [item["item_id"] for item in response.json()] == ["2", "3", "1"]

async def record_hits(session, hits: dict[str, int]) -> None:
    for key, times in hits.items():
        for _ in range(times):
            await increment_counter(session, SEARCH_HIT, key)


@pytest.mark.anyio
async def test_get_top_breaks_ties_by_key(client, session):
    # inserted in reverse order: only the second sort criterion puts "1" first
    await record_hits(session, {"streamer:2": 2, "streamer:1": 2})

    response = await client.get("/stats/search/top")

    assert response.status_code == HTTPStatus.OK
    assert [item["item_id"] for item in response.json()] == ["1", "2"]


@pytest.mark.anyio
async def test_get_top_filters_by_item_type(client, session):
    await record_hits(session, {"streamer:1": 1, "message:1": 5})

    response = await client.get("/stats/search/top", params={"item_type": "streamer"})

    assert response.status_code == HTTPStatus.OK
    items = response.json()
    assert len(items) == 1
    assert items[0]["item_type"] == "streamer"


@pytest.mark.anyio
async def test_get_top_respects_limit(client, session):
    await record_hits(session, {"streamer:1": 1, "streamer:2": 1, "streamer:3": 1})

    response = await client.get("/stats/search/top", params={"limit": 2})

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()) == 2


@pytest.mark.anyio
async def test_get_top_empty_database(client):
    response = await client.get("/stats/search/top")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@pytest.mark.anyio
@pytest.mark.parametrize("limit", [0, 501])
async def test_get_top_invalid_limit_returns_422(client, limit):
    response = await client.get("/stats/search/top", params={"limit": limit})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_on_search_hit_creates_then_increments_counter(
    client, session_factory, fake_redis, monkeypatch
):
    # the handler opens its own session: point it to the test database
    monkeypatch.setattr(handlers, "SessionLocal", session_factory)
    hit = SearchHit(
        item_type="streamer",
        item_id="42",
        query="saul",
        hit_at=datetime.now(UTC),
    )

    await on_search_hit(hit)
    first_response = await client.get("/stats/search/streamer/42")

    assert first_response.status_code == HTTPStatus.OK
    assert first_response.json()["count"] == 1

    await on_search_hit(hit)
    await fake_redis.flushall()
    second_response = await client.get("/stats/search/streamer/42")

    assert second_response.status_code == HTTPStatus.OK
    assert second_response.json()["count"] == 2