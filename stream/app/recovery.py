import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from common import topics
from common.events import StreamEnded, StreamStarted
from pydantic import ValidationError

from app import events
from app.live import STARTED_FILE

logger = logging.getLogger(__name__)

BROKER_WAIT_SECONDS = 30
BROKER_POLL_SECONDS = 1


def end_interrupted_lives(lives_dir: Path) -> list[StreamEnded]:
    """Ends the playlists a restart left open and returns the events to publish."""
    ended = []
    for playlist in sorted(lives_dir.glob("*/index.m3u8")):
        if "#EXT-X-ENDLIST" in playlist.read_text():
            continue
        # last write of ffmpeg, the closest we have to the real end of the live
        ended_at = datetime.fromtimestamp(playlist.stat().st_mtime, UTC)
        with playlist.open("a") as f:
            f.write("#EXT-X-ENDLIST\n")
        try:
            started = StreamStarted.model_validate_json(
                playlist.with_name(STARTED_FILE).read_text()
            )
        except (OSError, ValidationError) as exc:
            # missing or half written: one bad live must not stop the service from starting
            logger.warning(
                "Live %s ended without event, no usable %s: %s",
                playlist.parent.name, STARTED_FILE, exc,
            )
            continue
        ended.append(
            StreamEnded(
                stream_id=started.stream_id,
                streamer_id=started.streamer_id,
                ended_at=ended_at,
                duration_s=(ended_at - started.started_at).total_seconds(),
                reason="error",
            )
        )
    return ended


async def publish_ended(ended: list[StreamEnded]) -> None:
    if not ended:
        return
    # the MQTT client connects in the background, it is not ready right after the start
    waited = 0
    while not events.mqtt.connected and waited < BROKER_WAIT_SECONDS:
        await asyncio.sleep(BROKER_POLL_SECONDS)
        waited += BROKER_POLL_SECONDS
    for event in ended:
        await events.publish(topics.STREAM_ENDED, event)
