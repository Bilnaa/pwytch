import logging
from pathlib import Path

from common.events import StreamEnded, StreamStarted
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import replay_repository
from app.services.lives_storage import playlist_is_missing

logger = logging.getLogger(__name__)


async def on_stream_started(session: AsyncSession, event: StreamStarted) -> None:
    replay = await replay_repository.get_replay(session, event.stream_id)
    if replay is None:
        replay = await replay_repository.add_replay(session, event.stream_id)
    replay.streamer_id = event.streamer_id
    replay.streamer_name = event.streamer_name
    replay.title = event.title
    replay.game = event.game
    replay.started_at = event.started_at
    # ended_at et duration_s ne sont jamais touchés : stream/ended a pu arriver avant.
    await session.commit()


async def on_stream_ended(session: AsyncSession, event: StreamEnded, lives_dir: Path) -> None:
    replay = await replay_repository.get_replay(session, event.stream_id)
    if replay is not None and replay.ended_at is not None:
        logger.debug("Duplicate stream/ended ignored for live %s", event.stream_id)
        return
    if event.reason == "error" and playlist_is_missing(lives_dir, event.stream_id):
        if replay is not None:
            await replay_repository.delete_replay(session, replay)
            await session.commit()
        logger.info("Live %s ended with error and no playlist, no replay", event.stream_id)
        return
    if replay is None:
        replay = await replay_repository.add_replay(session, event.stream_id)
    replay.streamer_id = event.streamer_id
    replay.ended_at = event.ended_at
    replay.duration_s = event.duration_s
    await session.commit()
