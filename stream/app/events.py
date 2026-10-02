import logging

from common.events import BaseEvent
from common.mqtt import MqttClient, NotConnectedError

from app.config import settings

logger = logging.getLogger(__name__)

mqtt = MqttClient(settings.mqtt_host, settings.mqtt_port)


async def publish(topic: str, event: BaseEvent) -> None:
    try:
        await mqtt.publish(topic, event)
    except NotConnectedError as exc:
        # the broker being down must never stop a live
        logger.error("Event %s not published: %s (%s)", topic, exc, event)
