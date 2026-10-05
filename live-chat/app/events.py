import asyncio
import logging

from common.events import ChatMessage
from common.mqtt import MqttClient, NotConnectedError
from common.topics import CHAT_MESSAGE

from app.config import mqtt_settings
from app.models.message_model import MessageModel

logger = logging.getLogger(__name__)

mqtt = MqttClient(mqtt_settings.mqtt_host, mqtt_settings.mqtt_port)

# Keeps a reference to the publications in progress, otherwise asyncio may drop them
pending: set[asyncio.Task] = set()


def to_event(message: MessageModel) -> ChatMessage:
    return ChatMessage(
        message_id=message.id,
        stream_id=message.stream_id,
        author_id=message.author.id,
        author_name=message.author.username,
        content=message.content,
        sent_at=message.sent_at,
    )


async def publish(message: MessageModel) -> None:
    try:
        await mqtt.publish(CHAT_MESSAGE, to_event(message))
    except NotConnectedError as exc:
        # the broker being down must never stop the chat
        logger.error("Message %s not published: %s", message.id, exc)


def publish_in_background(message: MessageModel) -> None:
    # The chat loop doesn't wait for the broker: the next messages are not delayed
    task = asyncio.create_task(publish(message))
    pending.add(task)
    task.add_done_callback(pending.discard)


async def wait_pending() -> None:
    # On shutdown, the messages already accepted are still published; an unexpected
    # error in one of them must not stop the rest of the shutdown
    await asyncio.gather(*pending, return_exceptions=True)
