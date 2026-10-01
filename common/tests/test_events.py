from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from common.events import (
    BaseEvent,
    PlayerEvent,
    StreamEnded,
    StreamStarted,
)

NOW = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)

EVENTS = [
    StreamStarted(
        stream_id=1, streamer_id=2, streamer_name="alice", title="Speedrun", game="Celeste",
        started_at=NOW,
    ),
    StreamEnded(stream_id=1, streamer_id=2, ended_at=NOW, duration_s=12.5, reason="normal"),
    PlayerEvent(stream_id=1, event_type="play", user_id=None, occurred_at=NOW),
]


@pytest.mark.parametrize("event", EVENTS, ids=lambda event: type(event).__name__)
def test_event_survives_a_json_round_trip(event):
    restored = type(event).model_validate_json(event.model_dump_json())

    assert restored == event


def test_event_id_is_generated_and_unique():
    first = EVENTS[0]
    second = first.model_copy(update={"event_id": BaseEvent().event_id})

    assert isinstance(first.event_id, UUID)
    assert first.event_id != second.event_id


def test_event_id_is_serialized_as_a_string():
    assert isinstance(EVENTS[0].model_dump(mode="json")["event_id"], str)


def test_version_defaults_to_1():
    assert EVENTS[0].version == 1


def test_stream_ended_rejects_an_unknown_reason():
    with pytest.raises(ValidationError):
        StreamEnded(stream_id=1, streamer_id=2, ended_at=NOW, duration_s=1, reason="crash")


def test_player_event_rejects_an_unknown_type():
    with pytest.raises(ValidationError):
        PlayerEvent(stream_id=1, event_type="seek", user_id=1, occurred_at=NOW)


def test_missing_field_is_rejected():
    with pytest.raises(ValidationError):
        StreamStarted.model_validate_json('{"stream_id": 1}')
