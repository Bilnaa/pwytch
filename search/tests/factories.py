from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from common.events import ChatMessage, StreamEnded, StreamStarted
from sqlalchemy import func, select

STREAMER_ID = 1
FIRST_START = datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
SECOND_START = FIRST_START + timedelta(hours=1)
MESSAGE_ID = UUID("3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97")


def make_started(**overrides) -> StreamStarted:
    defaults = {
        "event_id": uuid4(),
        "stream_id": 1,
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
        "stream_id": 1,
        "streamer_id": STREAMER_ID,
        "ended_at": FIRST_START + timedelta(minutes=30),
        "duration_s": 1800,
        "reason": "normal",
    }
    return StreamEnded(**(defaults | overrides))


def make_chat_message(**overrides) -> ChatMessage:
    defaults = {
        "event_id": uuid4(),
        "message_id": MESSAGE_ID,
        "stream_id": 1,
        "author_id": 1,
        "author_name": "Célèste",
        "content": "GG WP !",
        "sent_at": FIRST_START,
    }
    return ChatMessage(**(defaults | overrides))


async def count_rows(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def reload(session, model, primary_key):
    # expire_on_commit=False garde les objets en mémoire : force une vraie relecture.
    session.expunge_all()
    return await session.get(model, primary_key)


def as_utc(naive_or_aware: datetime) -> datetime:
    # SQLite perd le fuseau à la relecture ; Postgres (timestamptz) le garde.
    return naive_or_aware.replace(tzinfo=UTC)
