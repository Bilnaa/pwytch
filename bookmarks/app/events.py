import logging

from common.events import BookmarkDeleted
from common.mqtt import MqttClient, NotConnectedError
from common.topics import BOOKMARK_DELETED

logger = logging.getLogger(__name__)


async def publish_bookmark_deleted(mqtt: MqttClient, event: BookmarkDeleted) -> None:
    try:
        await mqtt.publish(BOOKMARK_DELETED, event)
    except NotConnectedError as exc:
        logger.error("Publish bookmark %s failed: %s", event.bookmark_id, exc)

