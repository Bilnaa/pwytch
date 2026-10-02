from datetime import datetime, timezone

import pytest
from common import topics
from common.events import StreamEnded, StreamStarted
from sqlalchemy.orm import sessionmaker

from app.models import User
from app.mqtt import create_mqtt_client
from app.services import streams as streams_service

pytestmark = pytest.mark.anyio

STARTED_AT = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
ENDED_AT = datetime(2026, 10, 2, 13, tzinfo=timezone.utc)


@pytest.fixture
def mqtt(db_session):
    return create_mqtt_client(sessionmaker(bind=db_session.get_bind()))


@pytest.fixture
def stream(db_session):
    user = User(username="alice", display_name="alice", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    return streams_service.create_stream(db_session, user, "Speedrun", "Celeste")


def started(stream_id):
    return StreamStarted(
        stream_id=stream_id,
        streamer_id=1,
        streamer_name="alice",
        title="Speedrun",
        game="Celeste",
        started_at=STARTED_AT,
    ).model_dump_json()


def ended(stream_id):
    return StreamEnded(
        stream_id=stream_id,
        streamer_id=1,
        ended_at=ENDED_AT,
        duration_s=3600,
        reason="normal",
    ).model_dump_json()


async def test_stream_started_marks_the_stream_live(mqtt, db_session, stream):
    await mqtt.handle(topics.STREAM_STARTED, started(stream.id))

    db_session.refresh(stream)
    assert stream.status == "live"
    assert stream.started_at.replace(tzinfo=timezone.utc) == STARTED_AT


async def test_stream_ended_marks_the_stream_ended(mqtt, db_session, stream):
    await mqtt.handle(topics.STREAM_STARTED, started(stream.id))
    await mqtt.handle(topics.STREAM_ENDED, ended(stream.id))

    db_session.refresh(stream)
    assert stream.status == "ended"
    assert stream.ended_at.replace(tzinfo=timezone.utc) == ENDED_AT


async def test_unknown_stream_is_ignored(mqtt, caplog):
    await mqtt.handle(topics.STREAM_STARTED, started(999))
    await mqtt.handle(topics.STREAM_ENDED, ended(999))

    assert "unknown stream 999" in caplog.text
    assert "Handler failed" not in caplog.text


async def test_invalid_message_is_ignored(mqtt, db_session, stream):
    await mqtt.handle(topics.STREAM_STARTED, b"not json")

    db_session.refresh(stream)
    assert stream.status == "created"
