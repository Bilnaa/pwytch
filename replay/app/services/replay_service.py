from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from common.pagination import Page
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Mp4Status
from app.repositories.replay_repository import (
    claim_conversion,
    find_replay,
    list_replays,
    reset_conversion,
)
from app.schemas import ConversionPending, ReplayResult
from app.services.conversion_service import Mp4Converter
from app.services.exceptions import ConversionFailed, ReplayNotFound, VideoNotReady


@dataclass(frozen=True)
class Mp4Ready:
    """Le .mp4 existe : le routeur le sert en pièce jointe."""

    path: Path
    filename: str


async def list_replays_page(
    session: AsyncSession, page: int, size: int, streamer_id: int | None
) -> Page[ReplayResult]:
    replays, total = await list_replays(session, page, size, streamer_id)
    items = [ReplayResult.model_validate(replay, from_attributes=True) for replay in replays]
    return Page[ReplayResult](items=items, total=total, page=page, size=size)


async def get_replay(session: AsyncSession, stream_id: int) -> ReplayResult:
    replay = await find_replay(session, stream_id)
    if replay is None:
        raise ReplayNotFound
    return ReplayResult.model_validate(replay, from_attributes=True)


async def video_path(session: AsyncSession, converter: Mp4Converter, stream_id: int) -> Path:
    """Le .mp4 à lire dans le player ; jamais de conversion lancée ici."""
    replay = await find_replay(session, stream_id)
    if replay is None:
        raise ReplayNotFound
    mp4_path = converter.mp4_path(stream_id)
    if replay.mp4_status is not Mp4Status.READY or not mp4_path.is_file():
        raise VideoNotReady
    return mp4_path


async def prepare_download(
    session: AsyncSession,
    converter: Mp4Converter,
    schedule: Callable[..., object],
    stream_id: int,
) -> Mp4Ready | ConversionPending:
    """Sert le .mp4 s'il est prêt, sinon lance ou attend la conversion."""
    replay = await find_replay(session, stream_id)
    if replay is None:
        raise ReplayNotFound

    mp4_status = replay.mp4_status
    if mp4_status is Mp4Status.READY:
        mp4_path = converter.mp4_path(stream_id)
        if mp4_path.is_file():
            return Mp4Ready(path=mp4_path, filename=f"replay-{stream_id}.mp4")
        # Fichier supprimé ou volume perdu, on relance la conversion. Si une autre requête
        # l'a déjà fait, le claim ci-dessous échoue et on répond 202 sans second ffmpeg.
        await reset_conversion(session, stream_id, Mp4Status.READY)

    elif mp4_status is Mp4Status.FAILED:
        # L'échec est signalé une fois, par la requête qui remet à none ; la suivante relance
        # ffmpeg. Une requête arrivée trop tard trouve la conversion déjà repartie : 202.
        if await reset_conversion(session, stream_id, Mp4Status.FAILED):
            raise ConversionFailed

    # Tente le claim quel que soit le statut lu : seul none → processing en base gagne.
    if await claim_conversion(session, stream_id):
        # Lancée après l'envoi de la réponse, avec ses propres sessions.
        schedule(converter.convert, stream_id)

    return ConversionPending(stream_id=stream_id)
