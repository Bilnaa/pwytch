import asyncio
import logging

from common.events import BookmarkDeleted
from common.mqtt import MqttClient, NotConnectedError
from common.topics import BOOKMARK_DELETED

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 10
RETRY_DELAY_SECONDS = 5

async def publish_bookmark_deleted(mqtt: MqttClient, event: BookmarkDeleted) -> None:
    for attempt in range(MAX_ATTEMPTS):
        try:
            await mqtt.publish(BOOKMARK_DELETED, event)
            return
        except NotConnectedError as exc:
            logger.warning("Publish bookmark %s failed: %s", event.bookmark_id, exc)
            if attempt != MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
    logger.error("Publish bookmark %s failed", event.bookmark_id)

