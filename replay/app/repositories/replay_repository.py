from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Mp4Status, Replay

# Seul endroit qui dit ce qu'est un replay visible : un live terminé. duration_s est écrit avec
# ended_at ; une ligne écrite hors handler sans lui ferait planter ReplayResult (500).
FINISHED = and_(Replay.ended_at.is_not(None), Replay.duration_s.is_not(None))


async def find_replay(session: AsyncSession, stream_id: int) -> Replay | None:
    return await session.scalar(select(Replay).where(Replay.stream_id == stream_id, FINISHED))



async def get_replay(session: AsyncSession, stream_id: int) -> Replay | None:
    """Ligne du live, terminé ou non (find_replay ne voit que les replays terminés)."""
    return await session.get(Replay, stream_id)


async def add_replay(session: AsyncSession, stream_id: int) -> Replay:
    replay = Replay(stream_id=stream_id)
    session.add(replay)
    return replay


async def delete_replay(session: AsyncSession, replay: Replay) -> None:
    await session.delete(replay)

async def list_replays(
    session: AsyncSession, page: int, size: int, streamer_id: int | None
) -> tuple[list[Replay], int]:
    conditions = [FINISHED]
    if streamer_id is not None:
        conditions.append(Replay.streamer_id == streamer_id)

    total = await session.scalar(select(func.count()).select_from(Replay).where(*conditions))
    offset = (page - 1) * size
    if offset >= total:
        # Page au-delà de la fin : inutile de parcourir l'index pour renvoyer une liste vide.
        return [], total
    replays = await session.scalars(
        select(Replay)
        .where(*conditions)
        # Même ordre que l'index (ended_at, stream_id), lu à l'envers.
        .order_by(Replay.ended_at.desc(), Replay.stream_id.desc())
        .offset(offset)
        .limit(size)
    )
    return list(replays), total


async def claim_conversion(session: AsyncSession, stream_id: int) -> bool:
    """Passe none → processing en une requête : seul le gagnant lance ffmpeg."""
    result = await session.execute(
        update(Replay)
        .where(Replay.stream_id == stream_id, FINISHED, Replay.mp4_status == Mp4Status.NONE)
        .values(mp4_status=Mp4Status.PROCESSING)
    )
    await session.commit()
    return result.rowcount == 1


async def reset_conversion(
    session: AsyncSession, stream_id: int, expected_status: Mp4Status
) -> bool:
    """Remet à none seulement si la ligne a toujours le statut lu par la requête.

    Faux si une autre requête l'a déjà remise à none et a relancé ffmpeg : on n'écrase
    pas son processing, sinon deux ffmpeg écriraient le même .part.
    """
    result = await session.execute(
        update(Replay)
        .where(Replay.stream_id == stream_id, Replay.mp4_status == expected_status)
        .values(mp4_status=Mp4Status.NONE)
    )
    await session.commit()
    return result.rowcount == 1


async def finish_conversion(session: AsyncSession, stream_id: int, status: Mp4Status) -> bool:
    """Écrit le résultat seulement si la ligne est toujours « processing ».

    Faux si elle a été remise à none entre-temps : le résultat d'un ffmpeg qui finit en
    retard n'écrase pas un statut plus récent.
    """
    result = await session.execute(
        update(Replay)
        .where(Replay.stream_id == stream_id, Replay.mp4_status == Mp4Status.PROCESSING)
        .values(mp4_status=status)
    )
    await session.commit()
    return result.rowcount == 1


async def reset_processing(session: AsyncSession) -> int:
    """Au démarrage : une conversion « processing » a été tuée avec l'ancien process."""
    result = await session.execute(
        update(Replay)
        .where(Replay.mp4_status == Mp4Status.PROCESSING)
        .values(mp4_status=Mp4Status.NONE)
    )
    await session.commit()
    return result.rowcount


async def list_unconverted(session: AsyncSession) -> list[int]:
    """Au démarrage : replays terminés dont la conversion n'a jamais eu lieu ou a été tuée."""
    stream_ids = await session.scalars(
        select(Replay.stream_id).where(FINISHED, Replay.mp4_status == Mp4Status.NONE)
    )
    return list(stream_ids)
