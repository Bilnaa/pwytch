from datetime import UTC, datetime, timedelta
from uuid import uuid4

from common.events import StreamEnded, StreamStarted

from app.models import Replay

STREAMER_ID = 7
FIRST_START = datetime(2026, 10, 4, 20, 0, tzinfo=UTC)
FIRST_END = FIRST_START + timedelta(minutes=90)


async def add_replay(session, stream_id: int, **overrides) -> Replay:
    """Replay terminé par défaut ; ended_at=None donne un live en cours."""
    defaults = {
        "stream_id": stream_id,
        "streamer_id": STREAMER_ID,
        "streamer_name": "Célèste",
        "title": "Speedrun Any%",
        "game": "Celeste",
        "started_at": FIRST_START,
        "ended_at": FIRST_END,
        "duration_s": 5400.0,
    }
    replay = Replay(**(defaults | overrides))
    session.add(replay)
    await session.commit()
    return replay


async def reload(session, stream_id: int) -> Replay | None:
    # expire_on_commit=False garde les objets en mémoire : force une vraie relecture.
    session.expunge_all()
    return await session.get(Replay, stream_id)


def make_started(**overrides) -> StreamStarted:
    defaults = {
        "event_id": uuid4(),
        "stream_id": 42,
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
        "stream_id": 42,
        "streamer_id": STREAMER_ID,
        "ended_at": FIRST_END,
        "duration_s": 5400.0,
        "reason": "normal",
    }
    return StreamEnded(**(defaults | overrides))
