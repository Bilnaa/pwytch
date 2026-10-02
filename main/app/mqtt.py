import asyncio
from collections.abc import Awaitable, Callable

from common import topics
from common.events import BaseEvent, StreamEnded, StreamStarted
from common.mqtt import MqttClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import mqtt_settings
from app.db import SessionLocal
from app.services import streams as streams_service


def with_session[E: BaseEvent](
    session_factory: sessionmaker[Session], handler: Callable[[Session, E], None]
) -> Callable[[E], Awaitable[None]]:
    """Run a database handler in a thread, with its own session, for each event."""

    def run(event: E) -> None:
        with session_factory() as db:
            handler(db, event)

    async def on_event(event: E) -> None:
        # the database is synchronous: don't block the event loop
        await asyncio.to_thread(run, event)

    return on_event


def create_mqtt_client(session_factory: sessionmaker[Session] = SessionLocal) -> MqttClient:
    mqtt = MqttClient(mqtt_settings.mqtt_host, mqtt_settings.mqtt_port, client_id="main")
    mqtt.subscribe(
        topics.STREAM_STARTED,
        StreamStarted,
        with_session(session_factory, streams_service.on_stream_started),
    )
    mqtt.subscribe(
        topics.STREAM_ENDED,
        StreamEnded,
        with_session(session_factory, streams_service.on_stream_ended),
    )
    return mqtt
