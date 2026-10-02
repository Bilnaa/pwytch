import pytest
from app import mqtt as mqtt_module
from app.infra.config import Settings
from app.infra.models import IndexedChatMessage, Stream, Streamer
from app.mqtt import MQTT_CLIENT_ID, create_mqtt_client
from common.topics import CHAT_MESSAGE, STREAM_ENDED, STREAM_STARTED

from tests.factories import (
    MESSAGE_ID,
    STREAMER_ID,
    as_utc,
    count_rows,
    make_chat_message,
    make_ended,
    make_started,
)


@pytest.fixture
def mqtt(session_factory):
    return create_mqtt_client(Settings(), session_factory)


@pytest.mark.anyio
async def test_valid_started_indexes_the_streamer(mqtt, session_factory):
    await mqtt.handle(STREAM_STARTED, make_started().model_dump_json())

    # L'adaptateur ouvre et ferme sa propre session : relire avec une nouvelle session.
    async with session_factory() as session:
        streamer = await session.get(Streamer, STREAMER_ID)
    assert streamer is not None
    assert streamer.streamer_name == "Célèste"


@pytest.mark.anyio
async def test_valid_ended_sets_ended_at(mqtt, session_factory):
    ended = make_ended()

    await mqtt.handle(STREAM_ENDED, ended.model_dump_json())

    async with session_factory() as session:
        stream = await session.get(Stream, ended.stream_id)
    assert stream is not None
    assert as_utc(stream.ended_at) == ended.ended_at


@pytest.mark.anyio
async def test_valid_chat_message_is_indexed(mqtt, session_factory):
    await mqtt.handle(CHAT_MESSAGE, make_chat_message().model_dump_json())

    async with session_factory() as session:
        message = await session.get(IndexedChatMessage, MESSAGE_ID)
    assert message is not None
    assert message.content == "GG WP !"


@pytest.mark.anyio
async def test_failing_handler_leaves_no_row(monkeypatch, session_factory):
    # Remplacer le handler avant create_mqtt_client : l'abonnement garde la fonction
    # reçue à sa création.
    handled_events = []

    async def failing_handler(session, event) -> None:
        handled_events.append(event)
        session.add(
            Streamer(streamer_id=event.streamer_id, streamer_name="x", search_text="x")
        )
        await session.flush()
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(mqtt_module, "on_stream_started", failing_handler)
    mqtt = create_mqtt_client(Settings(), session_factory)
    started = make_started()

    await mqtt.handle(STREAM_STARTED, started.model_dump_json())

    # Sans ce contrôle, un payload refusé par la validation donnerait aussi 0 ligne.
    assert handled_events == [started]
    async with session_factory() as session:
        assert await count_rows(session, Streamer) == 0


@pytest.mark.anyio
async def test_client_uses_a_persistent_session(mqtt):
    assert mqtt.client_id == MQTT_CLIENT_ID == "search"
