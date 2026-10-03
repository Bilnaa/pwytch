import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Stream, User
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
    streams_service.mark_started(db_session, stream.id, utcnow())
    ended_at = utcnow()

    streams_service.mark_ended(db_session, stream.id, ended_at)

    assert stream.status == "ended"
    assert stream.ended_at == ended_at


def test_mark_unknown_stream_raises(db_session):
    with pytest.raises(streams_service.StreamNotFoundError):
        streams_service.mark_started(db_session, 999, utcnow())


def test_mark_started_ignores_a_cancelled_stream(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")
    stream.status = "cancelled"

    streams_service.mark_started(db_session, stream.id, utcnow())

    assert stream.status == "cancelled"
    assert stream.started_at is None


def test_mark_ended_ignores_a_stream_that_is_not_live(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")

    streams_service.mark_ended(db_session, stream.id, utcnow())

    assert stream.status == "created"
    assert stream.ended_at is None


def test_record_started_keeps_the_time_of_stream(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")
    streams_service.mark_started(db_session, stream.id, utcnow())
    started_at = utcnow()

    streams_service.record_started(db_session, stream.id, started_at)

    assert stream.status == "live"
    assert stream.started_at == started_at


def test_record_started_ignores_an_ended_stream(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")
    started_at = utcnow()
    streams_service.mark_started(db_session, stream.id, started_at)
    streams_service.mark_ended(db_session, stream.id, utcnow())

    streams_service.record_started(db_session, stream.id, utcnow())

    assert stream.status == "ended"
    assert stream.started_at == started_at


def test_mark_over_ends_a_live_stream(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")
    streams_service.mark_started(db_session, stream.id, utcnow())
    at = utcnow()

    streams_service.mark_over(db_session, stream.id, at)

    assert stream.status == "ended"
    assert stream.ended_at == at


def test_mark_over_cancels_a_created_stream(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")

    streams_service.mark_over(db_session, stream.id, utcnow())

    assert stream.status == "cancelled"
    assert stream.ended_at is None


def test_second_active_stream_is_rejected_by_the_database(db_session, streamer):
    streams_service.create_stream(db_session, streamer, "Title", "Game")
    db_session.add(Stream(streamer_id=streamer.id, title="Other", game="Game"))

    with pytest.raises(IntegrityError):
        db_session.commit()
