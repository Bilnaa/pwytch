import logging

import httpx
import pytest

from app.services.live_event_service import on_stream_ended, on_stream_started
from tests.factories import add_replay, make_ended, make_started, reload

PLAYLIST_PATH = "/lives/42/index.m3u8"


def stream_answering(status_code: int, requests: list | None = None) -> httpx.AsyncClient:
    def answer(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return httpx.Response(status_code)

    return httpx.AsyncClient(transport=httpx.MockTransport(answer), base_url="http://stream")


def unreachable_stream() -> httpx.AsyncClient:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(refuse), base_url="http://stream")


def warning_records(caplog):
    return [record for record in caplog.records if record.levelno == logging.WARNING]


@pytest.mark.anyio
async def test_started_alone_creates_a_hidden_row(session):
    await on_stream_started(session, make_started())

    stored_replay = await reload(session, 42)
    assert stored_replay.title == "Speedrun Any%"
    assert stored_replay.ended_at is None


@pytest.mark.anyio
async def test_started_then_ended_gives_a_full_replay(session):
    await on_stream_started(session, make_started())
    await on_stream_ended(session, make_ended(), stream_answering(200))

    stored_replay = await reload(session, 42)
    assert stored_replay.title == "Speedrun Any%"
    assert stored_replay.game == "Celeste"
    assert stored_replay.ended_at is not None
    assert stored_replay.duration_s == 5400.0


@pytest.mark.anyio
async def test_ended_then_started_gives_a_full_replay(session):
    await on_stream_ended(session, make_ended(), stream_answering(200))
    await on_stream_started(session, make_started())

    stored_replay = await reload(session, 42)
    assert stored_replay.streamer_name == "Célèste"
    assert stored_replay.ended_at is not None
    assert stored_replay.duration_s == 5400.0


@pytest.mark.anyio
async def test_ended_twice_keeps_the_first_end(session):
    await on_stream_ended(session, make_ended(duration_s=5400.0), stream_answering(200))
    await on_stream_ended(session, make_ended(duration_s=1.0), stream_answering(200))

    stored_replay = await reload(session, 42)
    assert stored_replay.duration_s == 5400.0


@pytest.mark.anyio
async def test_normal_end_does_not_call_stream(session):
    requests = []

    await on_stream_ended(session, make_ended(), stream_answering(404, requests))

    assert requests == []
    assert (await reload(session, 42)).ended_at is not None


@pytest.mark.anyio
async def test_error_end_with_playlist_creates_the_replay(session):
    requests = []

    await on_stream_ended(session, make_ended(reason="error"), stream_answering(200, requests))

    assert [(request.method, request.url.path) for request in requests] == [("HEAD", PLAYLIST_PATH)]
    assert (await reload(session, 42)).ended_at is not None


@pytest.mark.anyio
async def test_error_end_without_playlist_removes_the_row(session):
    await on_stream_started(session, make_started())

    await on_stream_ended(session, make_ended(reason="error"), stream_answering(404))

    assert await reload(session, 42) is None


@pytest.mark.anyio
async def test_error_end_with_stream_down_keeps_the_replay(session, caplog):
    await on_stream_ended(session, make_ended(reason="error"), unreachable_stream())

    assert (await reload(session, 42)).ended_at is not None
    assert len(warning_records(caplog)) == 1


@pytest.mark.anyio
async def test_error_end_with_stream_failing_keeps_the_replay(session, caplog):
    await on_stream_ended(session, make_ended(reason="error"), stream_answering(503))

    assert (await reload(session, 42)).ended_at is not None
    assert len(warning_records(caplog)) == 1


@pytest.mark.anyio
async def test_existing_replay_is_not_touched_by_a_late_error_end(session):
    await add_replay(session, 42)

    await on_stream_ended(session, make_ended(reason="error"), stream_answering(404))

    assert await reload(session, 42) is not None
