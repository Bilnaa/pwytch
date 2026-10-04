from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.text import normalize
from app.infra.models import (
    LATEST_STREAM_ORDER,
    IndexedChatMessage,
    Stream,
    Streamer,
)
from app.schemas import MessageResult, StreamerResult

CHAT_SEARCH_LIMIT = 10


def _latest_stream_field(column):
    return (
        select(column)
        .where(
            Stream.streamer_id == Streamer.streamer_id, Stream.started_at.is_not(None)
        )
        .order_by(*LATEST_STREAM_ORDER)
        .limit(1)
        .scalar_subquery()
    )


def _live_stream_id():
    return (
        select(Stream.stream_id)
        .where(
            Stream.streamer_id == Streamer.streamer_id,
            Stream.started_at.is_not(None),
            Stream.ended_at.is_(None),
        )
        .order_by(*LATEST_STREAM_ORDER)
        .limit(1)
        .scalar_subquery()
    )


async def search_streamers(
    session: AsyncSession, search_query: str, page: int, size: int
) -> tuple[list[StreamerResult], int]:
    matches_query = Streamer.search_text.contains(
        normalize(search_query), autoescape=True
    )

    count_result = await session.execute(
        select(func.count()).select_from(Streamer).where(matches_query)
    )
    total = count_result.scalar_one()

    live_stream_id = _live_stream_id().label("live_stream_id")
    is_live = live_stream_id.is_not(None).label("is_live")
    rows = await session.execute(
        select(
            Streamer.streamer_id,
            Streamer.streamer_name,
            _latest_stream_field(Stream.title).label("last_title"),
            _latest_stream_field(Stream.game).label("last_game"),
            is_live,
            live_stream_id,
        )
        .where(matches_query)
        .order_by(
            is_live.desc(), func.lower(Streamer.streamer_name), Streamer.streamer_id
        )
        .offset((page - 1) * size)
        .limit(size)
    )

    results = [StreamerResult.model_validate(row) for row in rows.mappings()]
    return results, total


async def search_chat_messages(
    session: AsyncSession, stream_id: int | None, search_query: str
) -> list[MessageResult]:
    """Cherche dans le chat d'un live, ou de tous les lives si stream_id est None."""
    conditions = [
        IndexedChatMessage.search_text.contains(
            normalize(search_query), autoescape=True
        )
    ]
    if stream_id is not None:
        conditions.append(IndexedChatMessage.stream_id == stream_id)
    statement = (
        select(IndexedChatMessage)
        .where(*conditions)
        # Même ordre que les index (..., sent_at, message_id), lus à l'envers.
        .order_by(
            IndexedChatMessage.sent_at.desc(), IndexedChatMessage.message_id.desc()
        )
        .limit(CHAT_SEARCH_LIMIT)
    )
    rows = await session.scalars(statement)
    return [
        MessageResult.model_validate(message, from_attributes=True) for message in rows
    ]
