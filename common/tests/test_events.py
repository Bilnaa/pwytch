from datetime import datetime

import pytest
from common.events import StreamEnded, StreamStarted
from pydantic import ValidationError


def make_stream_started_payload(**overrides):
    base = {
        "event_id": "0b6f8c1e-4a52-4f0e-9d3b-2f1a7c9e5d10",
        "stream_id": 42,
        "streamer_id": 3,
        "streamer_name": "Zerator",
        "title": "Speedrun any%",
        "game": "Celeste",
        "started_at": "2026-10-01T18:00:00Z",
    }
    return {**base, **overrides}


def make_stream_ended_payload(**overrides):
    base = {
        "event_id": "5c2d9a7e-1b3f-4e8a-a6c4-8d0e2f4b6a19",
        "stream_id": 42,
        "streamer_id": 3,
        "ended_at": "2026-10-01T20:00:00Z",
        "duration_s": 7200,
        "reason": "normal",
    }
    return {**base, **overrides}


def test_stream_started_is_built_from_valid_payload():
    event = StreamStarted.model_validate(make_stream_started_payload())

    assert event.streamer_name == "Zerator"
    assert isinstance(event.started_at, datetime)


def test_stream_started_round_trips_through_json():
    event = StreamStarted.model_validate(make_stream_started_payload())

    assert StreamStarted.model_validate_json(event.model_dump_json()) == event


def test_version_defaults_to_one():
    event = StreamStarted.model_validate(make_stream_started_payload())

    assert event.version == 1


def test_stream_started_without_streamer_name_is_rejected():
    payload = make_stream_started_payload()
    del payload["streamer_name"]

    with pytest.raises(ValidationError):
        StreamStarted.model_validate(payload)


def test_stream_ended_is_built_from_valid_payload():
    event = StreamEnded.model_validate(make_stream_ended_payload())

    assert event.duration_s == 7200
    assert event.reason == "normal"


def test_stream_ended_accepts_fractional_duration():
    event = StreamEnded.model_validate(make_stream_ended_payload(duration_s=12.5))

    assert event.duration_s == 12.5


def test_stream_ended_with_unknown_reason_is_rejected():
    with pytest.raises(ValidationError):
        StreamEnded.model_validate(make_stream_ended_payload(reason="crash"))


def test_event_with_invalid_event_id_is_rejected():
    with pytest.raises(ValidationError):
        StreamStarted.model_validate(
            make_stream_started_payload(event_id="pas-un-uuid")
        )
