from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.indexer import on_stream_ended, on_stream_started
from app.infra.models import Stream, Streamer
from common.events import StreamEnded, StreamStarted
from sqlalchemy import func, select

STREAMER_ID = "u1"
FIRST_START = datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
SECOND_START = FIRST_START + timedelta(hours=1)


def make_started(**overrides) -> StreamStarted:
    defaults = {
        "event_id": uuid4(),
        "stream_id": "s1",
        "streamer_id": STREAMER_ID,
        "streamer_name": "Célèste",
        "title": "Speedrun Any%",
        "game": "Celeste",
        "started_at": FIRST_START,
    }
    return StreamStarted(**(defaults | overrides))


def make_ended(**overrides) -> StreamEnded:
    defaults = {
        "event_id": uuid4(),
        "stream_id": "s1",
        "streamer_id": STREAMER_ID,
        "ended_at": FIRST_START + timedelta(minutes=30),
        "duration_s": 1800,
        "reason": "normal",
    }
    return StreamEnded(**(defaults | overrides))


async def count_rows(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def reload(session, model, primary_key):
    # expire_on_commit=False keeps objects in memory: force a real read from the database.
    session.expunge_all()
    return await session.get(model, primary_key)


def as_utc(naive_or_aware: datetime) -> datetime:
    # SQLite drops the timezone on read; Postgres (timestamptz) keeps it.
    return naive_or_aware.replace(tzinfo=UTC)


@pytest.mark.anyio
async def test_first_live_creates_streamer_and_stream(session):
    await on_stream_started(session, make_started())

    assert await count_rows(session, Streamer) == 1
    assert await count_rows(session, Stream) == 1
    streamer = await reload(session, Streamer, STREAMER_ID)
    assert streamer.streamer_name == "Célèste"
    assert streamer.search_text == "celeste | speedrun any% | celeste"


@pytest.mark.anyio
async def test_duplicate_started_is_idempotent(session):
    started = make_started()

    await on_stream_started(session, started)
    await on_stream_started(session, started)

    assert await count_rows(session, Streamer) == 1
    assert await count_rows(session, Stream) == 1
    streamer = await reload(session, Streamer, STREAMER_ID)
    assert streamer.search_text == "celeste | speedrun any% | celeste"


@pytest.mark.anyio
async def test_ended_sets_ended_at(session):
    ended = make_ended()

    await on_stream_started(session, make_started())
    await on_stream_ended(session, ended)

    stream = await reload(session, Stream, "s1")
    assert as_utc(stream.ended_at) == ended.ended_at
    assert stream.title == "Speedrun Any%"
    assert stream.game == "Celeste"
    assert as_utc(stream.started_at) == FIRST_START


@pytest.mark.anyio
async def test_duplicate_ended_is_idempotent(session):
    ended = make_ended()

    await on_stream_started(session, make_started())
    await on_stream_ended(session, ended)
    await on_stream_ended(session, ended)

    assert await count_rows(session, Stream) == 1
    stream = await reload(session, Stream, "s1")
    assert as_utc(stream.ended_at) == ended.ended_at


@pytest.mark.anyio
async def test_ended_before_started_keeps_both(session):
    ended = make_ended()

    await on_stream_ended(session, ended)
    await on_stream_started(session, make_started())

    stream = await reload(session, Stream, "s1")
    assert as_utc(stream.ended_at) == ended.ended_at
    assert stream.title == "Speedrun Any%"
    assert stream.game == "Celeste"
    assert as_utc(stream.started_at) == FIRST_START
    streamer = await session.get(Streamer, STREAMER_ID)
    assert streamer is not None
    assert streamer.search_text == "celeste | speedrun any% | celeste"


@pytest.mark.anyio
async def test_ended_alone_creates_no_streamer(session):
    await on_stream_ended(session, make_ended())

    assert await count_rows(session, Stream) == 1
    assert await count_rows(session, Streamer) == 0


@pytest.mark.anyio
async def test_older_started_does_not_override_latest(session):
    await on_stream_started(
        session,
        make_started(
            stream_id="s2",
            streamer_name="NewName",
            title="Nouveau",
            started_at=SECOND_START,
        ),
    )
    await on_stream_started(
        session,
        make_started(
            stream_id="s1",
            streamer_name="OldName",
            title="Ancien",
            started_at=FIRST_START,
        ),
    )

    streamer = await reload(session, Streamer, STREAMER_ID)
    assert "nouveau" in streamer.search_text
    assert "ancien" not in streamer.search_text
    assert "oldname" not in streamer.search_text
    assert streamer.streamer_name == "NewName"


@pytest.mark.anyio
async def test_new_live_replaces_search_text(session):
    await on_stream_started(
        session, make_started(stream_id="s1", title="Premier", started_at=FIRST_START)
    )
    await on_stream_ended(session, make_ended(stream_id="s1"))
    await on_stream_started(
        session, make_started(stream_id="s2", title="Second", started_at=SECOND_START)
    )

    streamer = await reload(session, Streamer, STREAMER_ID)
    assert "second" in streamer.search_text
    assert "premier" not in streamer.search_text


@pytest.mark.anyio
async def test_late_ended_of_previous_live_keeps_search_text(session):
    await on_stream_started(
        session, make_started(stream_id="s1", title="Premier", started_at=FIRST_START)
    )
    await on_stream_started(
        session, make_started(stream_id="s2", title="Second", started_at=SECOND_START)
    )
    await on_stream_ended(session, make_ended(stream_id="s1"))

    streamer = await reload(session, Streamer, STREAMER_ID)
    assert streamer.search_text == "celeste | second | celeste"


@pytest.mark.anyio
async def test_empty_game_still_builds_search_text(session):
    await on_stream_started(session, make_started(game=""))

    streamer = await reload(session, Streamer, STREAMER_ID)
    assert streamer.search_text == "celeste | speedrun any% |"
