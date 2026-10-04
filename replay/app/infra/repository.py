from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.models import Replay

# Seul endroit qui dit ce qu'est un replay visible : un live terminé.
FINISHED = Replay.ended_at.is_not(None)


async def find_replay(session: AsyncSession, stream_id: int) -> Replay | None:
    return await session.scalar(select(Replay).where(Replay.stream_id == stream_id, FINISHED))


async def list_replays(
    session: AsyncSession, page: int, size: int, streamer_id: int | None
) -> tuple[list[Replay], int]:
    conditions = [FINISHED]
    if streamer_id is not None:
        conditions.append(Replay.streamer_id == streamer_id)

    total = await session.scalar(select(func.count()).select_from(Replay).where(*conditions))
    replays = await session.scalars(
        select(Replay)
        .where(*conditions)
        # Même ordre que l'index (ended_at, stream_id), lu à l'envers.
        .order_by(Replay.ended_at.desc(), Replay.stream_id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(replays), total
