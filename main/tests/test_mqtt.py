from datetime import datetime, timezone

import pytest
from common import topics
from common.events import StreamEnded, StreamStarted

from app.mqtt import create_mqtt_client
from app.services import streams as streams_service

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def record_calls(monkeypatch, handler_name):
    calls = []

    async def handler(event):
        calls.append(event)

    monkeypatch.setattr(streams_service, handler_name, handler)
    return calls


async def test_stream_started_is_handled(monkeypatch):
    calls = record_calls(monkeypatch, "on_stream_started")
    event = StreamStarted(
        stream_id=3,
        streamer_id=7,
        streamer_name="john_doe",
        title="Speedrun",
        game="Celeste",
        started_at=NOW,
    )

    await create_mqtt_client().handle(topics.STREAM_STARTED, event.model_dump_json())

    assert calls == [event]


async def test_stream_ended_is_handled(monkeypatch):
    calls = record_calls(monkeypatch, "on_stream_ended")
    event = StreamEnded(
        stream_id=3, streamer_id=7, ended_at=NOW, duration_s=60, reason="normal"
    )

    await create_mqtt_client().handle(topics.STREAM_ENDED, event.model_dump_json())

    assert calls == [event]


async def test_invalid_message_is_ignored(monkeypatch):
    calls = record_calls(monkeypatch, "on_stream_started")

    await create_mqtt_client().handle(topics.STREAM_STARTED, b"not json")

    assert calls == []
