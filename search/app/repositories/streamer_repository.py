from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.text import normalize
from app.models import Stream, Streamer
from app.schemas import StreamerResult

# Dernier live d'un streamer : le plus récent démarré, puis le plus grand id.
LATEST_STREAM_ORDER = (Stream.started_at.desc(), Stream.stream_id.desc())


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


async def get_stream(session: AsyncSession, stream_id: int) -> Stream | None:
    return await session.get(Stream, stream_id)


async def add_stream(
    session: AsyncSession, stream_id: int, streamer_id: int | None = None
) -> Stream:
    stream = Stream(stream_id=stream_id, streamer_id=streamer_id)
    session.add(stream)
    return stream


async def find_latest_started_stream(session: AsyncSession, streamer_id: int) -> Stream | None:
    return await session.scalar(
        select(Stream)
        .where(Stream.streamer_id == streamer_id, Stream.started_at.is_not(None))
        .order_by(*LATEST_STREAM_ORDER)
        .limit(1)
    )


async def get_streamer(session: AsyncSession, streamer_id: int) -> Streamer | None:
    return await session.get(Streamer, streamer_id)


async def add_streamer(session: AsyncSession, streamer_id: int) -> Streamer:
    streamer = Streamer(streamer_id=streamer_id)
    session.add(streamer)
    return streamer
