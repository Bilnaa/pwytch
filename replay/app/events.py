import logging

import httpx
from common.events import StreamEnded, StreamStarted
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.models import Replay

logger = logging.getLogger(__name__)


async def on_stream_started(session: AsyncSession, event: StreamStarted) -> None:
    replay = await _get_or_create_replay(session, event.stream_id)
    replay.streamer_id = event.streamer_id
    replay.streamer_name = event.streamer_name
    replay.title = event.title
    replay.game = event.game
    replay.started_at = event.started_at
    # ended_at et duration_s ne sont jamais touchés : stream/ended a pu arriver avant.
    await session.commit()


async def on_stream_ended(
    session: AsyncSession, event: StreamEnded, stream_client: httpx.AsyncClient
) -> None:
    replay = await session.get(Replay, event.stream_id)
    if replay is not None and replay.ended_at is not None:
        logger.debug("Duplicate stream/ended ignored for live %s", event.stream_id)
        return
    if event.reason == "error" and await playlist_is_missing(
        stream_client, event.stream_id
    ):
        if replay is not None:
            await session.delete(replay)
            await session.commit()
        logger.info(
            "Live %s ended with error and no playlist, no replay", event.stream_id
        )
        return
    if replay is None:
        replay = Replay(stream_id=event.stream_id)
        session.add(replay)
    replay.streamer_id = event.streamer_id
    replay.ended_at = event.ended_at
    replay.duration_s = event.duration_s
    await session.commit()


async def playlist_is_missing(stream_client: httpx.AsyncClient, stream_id: int) -> bool:
    """Vrai seulement si stream répond 404 : dans le doute, le replay est gardé."""
    try:
        response = await stream_client.head(f"/lives/{stream_id}/index.m3u8")
    except httpx.HTTPError as exc:
        logger.warning(
            "Playlist of live %s not checked, replay kept: %s", stream_id, exc
        )
        return False
    if response.status_code == 404:
        return True
    if not response.is_success:
        logger.warning(
            "Playlist of live %s not checked (HTTP %s), replay kept",
            stream_id,
            response.status_code,
        )
    return False


async def _get_or_create_replay(session: AsyncSession, stream_id: int) -> Replay:
    replay = await session.get(Replay, stream_id)
    if replay is None:
        replay = Replay(stream_id=stream_id)
        session.add(replay)
    return replay
