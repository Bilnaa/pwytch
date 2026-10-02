import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiomqtt
from common.events import BaseEvent, StreamEnded, StreamStarted
from common.topics import STREAM_ENDED, STREAM_STARTED
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.indexer import on_stream_ended, on_stream_started
from app.infra.config import Settings

logger = logging.getLogger(__name__)

SUBSCRIBED_TOPICS = (STREAM_STARTED, STREAM_ENDED)
FIRST_RECONNECT_DELAY_S = 1
MAX_RECONNECT_DELAY_S = 30

type EventHandler = Callable[[AsyncSession, Any], Awaitable[None]]


def _routes() -> dict[str, tuple[type[BaseEvent], EventHandler]]:
    # Construit à chaque appel, pas à l'import : les handlers sont relus à chaque
    # message, donc un handler remplacé par monkeypatch est bien celui appelé.
    return {
        STREAM_STARTED: (StreamStarted, on_stream_started),
        STREAM_ENDED: (StreamEnded, on_stream_ended),
    }


async def dispatch(
    session_factory: async_sessionmaker[AsyncSession], topic: str, payload: bytes
) -> None:
    """Valide un message et lance son handler. Ne lève jamais (sauf annulation)."""
    route = _routes().get(topic)
    if route is None:
        logger.debug("Ignoring message on unknown topic %s", topic)
        return
    event_model, handler = route

    # JSON invalide et champ manquant lèvent tous deux ValidationError.
    try:
        event = event_model.model_validate_json(payload)
    except ValidationError as error:
        logger.warning("Invalid payload on topic %s: %s", topic, error)
        return

    # except Exception laisse passer asyncio.CancelledError : le lifespan peut
    # arrêter le consumer avec task.cancel().
    try:
        # Sortir du bloc ferme la session, ce qui annule une transaction non commitée.
        async with session_factory() as session:
            await handler(session, event)
    except Exception:
        logger.exception(
            "Handler failed for event %s on topic %s", event.event_id, topic
        )


async def run_consumer(
    app_settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    reconnect_delay = FIRST_RECONNECT_DELAY_S
    while True:
        try:
            async with aiomqtt.Client(
                app_settings.mqtt_host, app_settings.mqtt_port
            ) as client:
                for topic in SUBSCRIBED_TOPICS:
                    await client.subscribe(topic, qos=1)
                logger.info("Subscribed to %s", ", ".join(SUBSCRIBED_TOPICS))
                reconnect_delay = FIRST_RECONNECT_DELAY_S
                async for message in client.messages:
                    await dispatch(
                        session_factory, message.topic.value, message.payload
                    )
        except aiomqtt.MqttError as error:
            logger.warning(
                "MQTT connection lost (%s), retrying in %s s", error, reconnect_delay
            )
        except Exception:
            # Garde : sans elle, une erreur inattendue terminerait la tâche de fond en
            # silence (l'API répond toujours, mais l'index ne bouge plus). On logue et
            # on repart comme après une coupure. CancelledError passe toujours.
            logger.exception(
                "MQTT consumer crashed, restarting in %s s", reconnect_delay
            )
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY_S)
