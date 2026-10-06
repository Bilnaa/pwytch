from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from common.events import PlayerEvent
from common.topics import PLAYER_EVENT

from app import handlers
from app.counters import increment_counter
from app.handlers import on_player_event
from app.utils import LIMIT_INTEGER


async def record_events(session, events: dict[str, int]) -> None:
    for key, times in events.items():
        for _ in range(times):
            await increment_counter(session, PLAYER_EVENT, key)


@pytest.mark.anyio
@pytest.mark.parametrize("stream_id", ["abc", "0", str(LIMIT_INTEGER + 1)])
async def test_get_player_stats_invalid_stream_id_returns_422(client, stream_id):
    response = await client.get(f"/stats/player/{stream_id}")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.anyio
async def test_get_player_stats_without_events_returns_zeros(client):
    response = await client.get("/stats/player/1")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"stream_id": 1, "play": 0, "pause": 0, "stop": 0}


@pytest.mark.anyio
async def test_get_player_stats_only_play(client, session):
    await record_events(session, {"5:play": 3})

    response = await client.get("/stats/player/5")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"stream_id": 5, "play": 3, "pause": 0, "stop": 0}


@pytest.mark.anyio
async def test_get_player_stats_all_event_types(client, session):
    await record_events(session, {"5:play": 4, "5:pause": 2, "5:stop": 1})

    response = await client.get("/stats/player/5")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"stream_id": 5, "play": 4, "pause": 2, "stop": 1}


@pytest.mark.anyio
async def test_get_player_stats_does_not_mix_streams(client, session):
    # "1:" must not match "12:"
    await record_events(session, {"1:play": 1, "12:play": 5, "12:stop": 2})

    response = await client.get("/stats/player/1")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"stream_id": 1, "play": 1, "pause": 0, "stop": 0}


@pytest.mark.anyio
async def test_on_player_event_creates_then_increments_counter(
    client, session_factory, fake_redis, monkeypatch
):
    # the handler opens its own session: point it to the test database
    monkeypatch.setattr(handlers, "SessionLocal", session_factory)
    event = PlayerEvent(
        stream_id=42,
        event_type="play",
        user_id=1,
        occurred_at=datetime.now(UTC),
    )

    await on_player_event(event)
    first_response = await client.get("/stats/player/42")

    assert first_response.status_code == HTTPStatus.OK
    assert first_response.json()["play"] == 1

    await on_player_event(event)
    await fake_redis.flushall()
    second_response = await client.get("/stats/player/42")

    assert second_response.status_code == HTTPStatus.OK
    assert second_response.json()["play"] == 2
