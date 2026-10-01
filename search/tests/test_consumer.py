import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from app.consumer import dispatch, run_consumer
from app.infra.config import Settings
from app.infra.models import Stream, Streamer
from common.topics import STREAM_ENDED, STREAM_STARTED

from tests.factories import (
    STREAMER_ID,
    as_utc,
    count_rows,
    make_ended,
    make_started,
)


def to_payload(event) -> bytes:
    return event.model_dump_json().encode()


async def failing_handler(session, event) -> None:
    session.add(
        Streamer(streamer_id=event.streamer_id, streamer_name="x", search_text="x")
    )
    await session.flush()
    raise RuntimeError("database unavailable")


@pytest.mark.anyio
async def test_valid_started_indexes_the_streamer(session_factory):
    await dispatch(session_factory, STREAM_STARTED, to_payload(make_started()))

    # dispatch ouvre et ferme sa propre session : relire avec une nouvelle session.
    async with session_factory() as session:
        streamer = await session.get(Streamer, STREAMER_ID)
    assert streamer is not None
    assert streamer.streamer_name == "Célèste"


@pytest.mark.anyio
async def test_valid_ended_sets_ended_at(session_factory):
    ended = make_ended()

    await dispatch(session_factory, STREAM_ENDED, to_payload(ended))

    async with session_factory() as session:
        stream = await session.get(Stream, "s1")
    assert stream is not None
    assert as_utc(stream.ended_at) == ended.ended_at


@pytest.mark.anyio
async def test_invalid_json_logs_warning_with_topic(session_factory, caplog):
    await dispatch(session_factory, STREAM_STARTED, b"{pas du json")

    [record] = caplog.records
    assert record.levelname == "WARNING"
    assert STREAM_STARTED in record.getMessage()


@pytest.mark.anyio
async def test_payload_missing_field_logs_warning(session_factory, caplog):
    payload_fields = make_started().model_dump(mode="json")
    del payload_fields["streamer_id"]

    await dispatch(session_factory, STREAM_STARTED, json.dumps(payload_fields).encode())

    [record] = caplog.records
    assert record.levelname == "WARNING"
    assert STREAM_STARTED in record.getMessage()
    async with session_factory() as session:
        assert await count_rows(session, Streamer) == 0


@pytest.mark.anyio
async def test_unknown_topic_leaves_database_unchanged(session_factory):
    await dispatch(session_factory, "autre/topic", to_payload(make_started()))

    async with session_factory() as session:
        assert await count_rows(session, Streamer) == 0
        assert await count_rows(session, Stream) == 0


@pytest.mark.anyio
async def test_handler_error_logs_error_with_event_id(
    session_factory, caplog, monkeypatch
):
    monkeypatch.setattr("app.consumer.on_stream_started", failing_handler)
    started = make_started()

    await dispatch(session_factory, STREAM_STARTED, to_payload(started))

    [record] = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert record.levelname == "ERROR"
    assert str(started.event_id) in record.getMessage()
    async with session_factory() as session:
        assert await count_rows(session, Streamer) == 0


class CrashingClient:
    # Faux client MQTT : l'entrée dans le bloc lève une erreur autre que MqttError.
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        raise RuntimeError("unexpected failure")

    async def __aexit__(self, *exc_info):
        return False


@pytest.mark.anyio
async def test_consumer_survives_unexpected_errors(
    session_factory, caplog, monkeypatch
):
    waited_delays = []

    async def fake_sleep(delay):
        waited_delays.append(delay)
        if len(waited_delays) == 3:
            # Simule l'arrêt du lifespan (task.cancel()) pour sortir de la boucle.
            raise asyncio.CancelledError

    monkeypatch.setattr("app.consumer.aiomqtt.Client", CrashingClient)
    # Remplace asyncio dans consumer.py seulement, pas dans la boucle de pytest.
    monkeypatch.setattr("app.consumer.asyncio", SimpleNamespace(sleep=fake_sleep))

    with pytest.raises(asyncio.CancelledError):
        await run_consumer(Settings(), session_factory)

    assert waited_delays == [1, 2, 4]
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_records) == 3
