"""Event builders and database helpers shared by the test modules."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from common.events import StreamEnded, StreamStarted

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


async def reload(session, model, primary_key):
    # expire_on_commit=False keeps objects in memory: force a real read from the database.
    session.expunge_all()
    return await session.get(model, primary_key)


def as_utc(naive_or_aware: datetime) -> datetime:
    # SQLite drops the timezone on read; Postgres (timestamptz) keeps it.
    return naive_or_aware.replace(tzinfo=UTC)
