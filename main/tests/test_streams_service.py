import pytest

from app.models import User
from app.models.stream import utcnow
from app.services import streams as streams_service


@pytest.fixture
def streamer(db_session):
    user = User(username="alice", display_name="alice", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    return user


def test_mark_started_sets_live_and_started_at(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")
    started_at = utcnow()

    streams_service.mark_started(db_session, stream.id, started_at)

    assert stream.status == "live"
    assert stream.started_at == started_at


def test_mark_ended_sets_ended_and_ended_at(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")
    ended_at = utcnow()

    streams_service.mark_ended(db_session, stream.id, ended_at)

    assert stream.status == "ended"
    assert stream.ended_at == ended_at


def test_mark_unknown_stream_raises(db_session):
    with pytest.raises(streams_service.StreamNotFoundError):
        streams_service.mark_started(db_session, 999, utcnow())
