from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.text import normalize
from app.infra.models import LATEST_STREAM_ORDER, Stream, Streamer
from app.schemas import StreamerResult


def _latest_stream_field(column):
    # Last live (spec 6.4): the stream with the greatest non-null started_at.
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
    # Live (spec 6.4): started and not ended; the latest one if an ended was lost.
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
