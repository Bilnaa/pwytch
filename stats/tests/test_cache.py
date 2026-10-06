from http import HTTPStatus

import fakeredis
import pytest
from common.topics import SEARCH_HIT

from app.cache import CACHE_TTL_SECONDS, get_redis
from app.counters import increment_counter
from app.main import app

ALL_ROUTES = [
    "/stats/search/top",
    "/stats/search/streamer/1",
    "/stats/bookmarks/deleted/top",
    "/stats/bookmarks/deleted/replay/1",
    "/stats/chat/top",
    "/stats/chat/1",
    "/stats/player/1",
]


@pytest.mark.anyio
@pytest.mark.parametrize("url", ALL_ROUTES)
async def test_first_call_is_a_miss_then_a_hit(client, url):
    first = await client.get(url)
    second = await client.get(url)

    assert first.status_code == HTTPStatus.OK
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert second.json() == first.json()


@pytest.mark.anyio
async def test_cached_value_has_a_short_lifetime(client, fake_redis):
    await client.get("/stats/search/top")

    ttl = await fake_redis.ttl("stats:/stats/search/top")

    assert 0 < ttl <= CACHE_TTL_SECONDS


@pytest.mark.anyio
async def test_different_params_use_different_entries(client):
    await client.get("/stats/search/top", params={"limit": 3})

    response = await client.get("/stats/search/top", params={"limit": 5})

    assert response.headers["X-Cache"] == "MISS"


@pytest.mark.anyio
async def test_params_order_does_not_matter(client):
    await client.get("/stats/search/top?limit=3&item_type=streamer")

    response = await client.get("/stats/search/top?item_type=streamer&limit=3")

    assert response.headers["X-Cache"] == "HIT"


@pytest.mark.anyio
async def test_value_is_read_again_from_database_after_expiry(
    client, session, fake_redis
):
    await increment_counter(session, SEARCH_HIT, "streamer:42")
    first = await client.get("/stats/search/streamer/42")

    await increment_counter(session, SEARCH_HIT, "streamer:42")
    # before the expiry: the cache still answers the old value
    still_cached = await client.get("/stats/search/streamer/42")
    # simulate the expiry instead of waiting CACHE_TTL_SECONDS
    await fake_redis.flushall()
    after_expiry = await client.get("/stats/search/streamer/42")

    assert first.json()["count"] == 1
    assert still_cached.headers["X-Cache"] == "HIT"
    assert still_cached.json()["count"] == 1
    assert after_expiry.headers["X-Cache"] == "MISS"
    assert after_expiry.json()["count"] == 2


@pytest.mark.anyio
async def test_invalid_request_is_not_cached(client, fake_redis):
    response = await client.get("/stats/chat/abc")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert await fake_redis.keys("*") == []


@pytest.mark.anyio
@pytest.mark.parametrize("url", ALL_ROUTES)
async def test_routes_work_when_redis_is_down(client, url):
    server = fakeredis.FakeServer()
    server.connected = False
    app.dependency_overrides[get_redis] = lambda: fakeredis.FakeAsyncRedis(
        server=server, decode_responses=True
    )

    response = await client.get(url)

    assert response.status_code == HTTPStatus.OK
    assert response.headers["X-Cache"] == "MISS"