from collections.abc import Awaitable, Callable

from common.events import BaseEvent, ChatMessage, StreamEnded, StreamStarted
from common.mqtt import MqttClient
from common.topics import CHAT_MESSAGE, STREAM_ENDED, STREAM_STARTED
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.indexer import on_chat_message, on_stream_ended, on_stream_started
from app.infra.config import Settings

# Avec un client_id, le broker garde les messages QoS 1 reçus pendant un redémarrage.
MQTT_CLIENT_ID = "search"


def with_session[E: BaseEvent](
    session_factory: async_sessionmaker[AsyncSession],
    handler: Callable[[AsyncSession, E], Awaitable[None]],
) -> Callable[[E], Awaitable[None]]:
    """Lance un handler de base de données avec sa propre session, pour chaque event."""

    async def on_event(event: E) -> None:
        # Sortir du bloc ferme la session, ce qui annule une transaction non commitée.
        async with session_factory() as session:
            await handler(session, event)

    return on_event


def create_mqtt_client(
    app_settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> MqttClient:
    mqtt = MqttClient(
        app_settings.mqtt_host, app_settings.mqtt_port, client_id=MQTT_CLIENT_ID
    )
    mqtt.subscribe(
        STREAM_STARTED, StreamStarted, with_session(session_factory, on_stream_started)
    )
    mqtt.subscribe(
        STREAM_ENDED, StreamEnded, with_session(session_factory, on_stream_ended)
    )
    mqtt.subscribe(
        CHAT_MESSAGE, ChatMessage, with_session(session_factory, on_chat_message)
    )
    return mqtt
