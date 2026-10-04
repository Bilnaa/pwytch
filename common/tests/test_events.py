from datetime import datetime
from uuid import UUID

import pytest
from common.events import (
    ChatMessage,
    ItemType,
    PlayerEvent,
    SearchHit,
    StreamEnded,
    StreamStarted,
)
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


def test_event_id_is_generated_when_missing():
    payload = make_stream_ended_payload()
    del payload["event_id"]

    first = StreamEnded.model_validate(payload)
    second = StreamEnded.model_validate(payload)

    assert first.event_id != second.event_id


def make_player_event_payload(**overrides):
    base = {
        "stream_id": 42,
        "event_type": "play",
        "user_id": None,
        "occurred_at": "2026-10-01T18:05:00Z",
    }
    return {**base, **overrides}


def test_player_event_accepts_an_anonymous_viewer():
    event = PlayerEvent.model_validate(make_player_event_payload())

    assert event.user_id is None


def test_player_event_round_trips_through_json():
    event = PlayerEvent.model_validate(make_player_event_payload(user_id=3))

    assert PlayerEvent.model_validate_json(event.model_dump_json()) == event


def test_player_event_with_unknown_type_is_rejected():
    with pytest.raises(ValidationError):
        PlayerEvent.model_validate(make_player_event_payload(event_type="seek"))


def make_chat_message_payload(**overrides):
    base = {
        "event_id": "9e4a1c7b-3d5f-4b2a-8c6e-1f0d2b4a6c83",
        "message_id": "3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97",
        "stream_id": 42,
        "author_id": 7,
        "author_name": "Célèste",
        "content": "GG WP !",
        "sent_at": "2026-10-02T20:14:03Z",
    }
    return {**base, **overrides}


def test_chat_message_is_built_from_valid_payload():
    event = ChatMessage.model_validate(make_chat_message_payload())

    assert event.event_id == UUID("9e4a1c7b-3d5f-4b2a-8c6e-1f0d2b4a6c83")
    assert event.message_id == UUID("3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97")
    assert event.author_name == "Célèste"
    assert isinstance(event.sent_at, datetime)
    assert event.sent_at.tzinfo is not None


def test_chat_message_round_trips_through_json():
    event = ChatMessage.model_validate(make_chat_message_payload())

    assert ChatMessage.model_validate_json(event.model_dump_json()) == event


def test_chat_message_content_is_stripped():
    event = ChatMessage.model_validate(make_chat_message_payload(content="  gg wp  "))

    assert event.content == "gg wp"


def test_chat_message_accepts_content_of_500_characters():
    event = ChatMessage.model_validate(make_chat_message_payload(content="x" * 500))

    assert len(event.content) == 500


def test_chat_message_without_content_is_rejected():
    payload = make_chat_message_payload()
    del payload["content"]

    with pytest.raises(ValidationError):
        ChatMessage.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        {"content": ""},
        {"content": "   "},
        {"content": "x" * 501},
        {"author_name": ""},
        {"message_id": "pas-un-uuid"},
        {"message_id": 1203},
        {"sent_at": "2026-10-02T20:14:03"},
    ],
    ids=[
        "empty-content",
        "blank-content",
        "content-too-long",
        "empty-author-name",
        "message-id-not-a-uuid",
        "message-id-integer",
        "sent-at-without-timezone",
    ],
)
def test_chat_message_with_invalid_field_is_rejected(overrides):
    with pytest.raises(ValidationError):
        ChatMessage.model_validate(make_chat_message_payload(**overrides))


def make_search_hit_payload(**overrides):
    base = {
        "event_id": "8c1f5e2a-6b3d-4f7a-9e0c-2d4b6a8f1c35",
        "item_type": "streamer",
        "item_id": "42",
        "query": "zera",
        "hit_at": "2026-10-03T14:02:11Z",
    }
    return {**base, **overrides}


def test_search_hit_is_built_from_valid_payload():
    event = SearchHit.model_validate(make_search_hit_payload())

    assert event.item_type is ItemType.STREAMER
    assert event.item_id == "42"
    assert event.query == "zera"
    assert event.hit_at.tzinfo is not None


def test_search_hit_accepts_message_type():
    event = SearchHit.model_validate(make_search_hit_payload(item_type="message"))

    assert event.item_type is ItemType.MESSAGE


def test_search_hit_serializes_item_type_as_its_value():
    event = SearchHit.model_validate(make_search_hit_payload())

    assert '"item_type":"streamer"' in event.model_dump_json()


def test_search_hit_round_trips_through_json():
    event = SearchHit.model_validate(make_search_hit_payload())

    assert SearchHit.model_validate_json(event.model_dump_json()) == event


@pytest.mark.parametrize(
    "overrides",
    [
        {"item_type": "video"},
        {"item_id": ""},
        {"query": ""},
        {"hit_at": "2026-10-03T14:02:11"},
    ],
    ids=[
        "unknown-item-type",
        "empty-item-id",
        "empty-query",
        "hit-at-without-timezone",
    ],
)
def test_search_hit_with_invalid_field_is_rejected(overrides):
    with pytest.raises(ValidationError):
        SearchHit.model_validate(make_search_hit_payload(**overrides))
