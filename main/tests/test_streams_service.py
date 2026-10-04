from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

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


ENDED_PLAYLIST = "#EXTM3U\n#EXTINF:4.000000,\nindex0.ts\n#EXT-X-ENDLIST\n"
LAST_SEGMENT = "Sun, 04 Oct 2026 10:15:30 GMT"


def stream_client(running=(), playlists=None, last_modified=LAST_SEGMENT):
    playlists = playlists or {}
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/streams":
            return httpx.Response(200, json=list(running))
        stream_id = int(request.url.path.split("/")[2])
        if stream_id not in playlists:
            return httpx.Response(404)
        headers = {"last-modified": last_modified} if last_modified else {}
        return httpx.Response(200, text=playlists[stream_id], headers=headers)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://stream")
    return client, calls


@pytest.fixture
def live_stream(db_session, streamer):
    stream = streams_service.create_stream(db_session, streamer, "Title", "Game")
    streams_service.mark_started(db_session, stream.id, datetime(2026, 10, 4, 10, tzinfo=UTC))
    return stream


@pytest.fixture
def session_factory(db_session):
    return sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)


def status_of(db_session, stream):
    db_session.expire_all()
    return db_session.get(Stream, stream.id)


@pytest.mark.anyio
async def test_end_missed_lives_ends_a_finished_playlist_at_its_last_segment(
    db_session, live_stream, session_factory
):
    client, _ = stream_client(playlists={live_stream.id: ENDED_PLAYLIST})

    async with client:
        await streams_service.end_missed_lives(client, session_factory)

    stream = status_of(db_session, live_stream)
    assert stream.status == "ended"
    assert stream.ended_at.replace(tzinfo=UTC) == datetime(2026, 10, 4, 10, 15, 30, tzinfo=UTC)


@pytest.mark.anyio
async def test_end_missed_lives_skips_a_live_still_running_on_stream(
    db_session, live_stream, session_factory
):
    client, calls = stream_client(
        running=[live_stream.id], playlists={live_stream.id: ENDED_PLAYLIST}
    )

    async with client:
        await streams_service.end_missed_lives(client, session_factory)

    assert status_of(db_session, live_stream).status == "live"
    assert calls == ["/streams"]


@pytest.mark.anyio
async def test_end_missed_lives_keeps_a_playlist_without_endlist(
    db_session, live_stream, session_factory
):
    client, _ = stream_client(playlists={live_stream.id: "#EXTM3U\n"})

    async with client:
        await streams_service.end_missed_lives(client, session_factory)

    assert status_of(db_session, live_stream).status == "live"


@pytest.mark.anyio
async def test_end_missed_lives_keeps_a_live_without_playlist(
    db_session, live_stream, session_factory
):
    client, _ = stream_client()

    async with client:
        await streams_service.end_missed_lives(client, session_factory)

    assert status_of(db_session, live_stream).status == "live"


@pytest.mark.anyio
async def test_end_missed_lives_uses_now_without_last_modified(
    db_session, live_stream, session_factory
):
    client, _ = stream_client(playlists={live_stream.id: ENDED_PLAYLIST}, last_modified=None)
    before = utcnow()

    async with client:
        await streams_service.end_missed_lives(client, session_factory)

    stream = status_of(db_session, live_stream)
    assert stream.status == "ended"
    assert stream.ended_at.replace(tzinfo=UTC) >= before.replace(microsecond=0)


@pytest.mark.anyio
async def test_end_missed_lives_does_not_call_stream_without_live(db_session, session_factory):
    client, calls = stream_client()

    async with client:
        await streams_service.end_missed_lives(client, session_factory)

    assert calls == []
