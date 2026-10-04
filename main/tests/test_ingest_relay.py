import pytest
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError

from app.models import Stream
from app.services import ingest
from tests.fakes import FakeUpstream, close_code, create_stream


def test_chunks_are_forwarded_unchanged(client, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"\x1a\x45\xdf\xa3")
        ws.send_bytes(b"second chunk")

    assert upstream.chunks == [b"\x1a\x45\xdf\xa3", b"second chunk"]
    assert upstream.exited


def test_stream_receives_the_metadata(client, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")

    url = upstream.urls[0]
    assert f"/streams/{stream_id}/ingest?" in url
    assert url.startswith("ws://")
    assert "streamer_name=alice" in url
    assert "title=Speedrun+any%25" in url
    assert "game=Celeste" in url
    assert "streamer_id=" in url


def test_streamer_can_reconnect_to_a_live_stream(client, db_session, upstream):
    stream_id, token = create_stream(client)
    db_session.get(Stream, stream_id).status = "live"
    db_session.commit()

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"again")

    assert upstream.chunks == [b"again"]


def test_stream_down_closes_with_1011(client, monkeypatch):
    monkeypatch.setattr(ingest, "connect", FakeUpstream(connect_error=ConnectionRefusedError()))
    stream_id, token = create_stream(client)

    assert close_code(client, f"/api/streams/{stream_id}/ingest?token={token}") == 1011


def closed_by_stream(client, monkeypatch, code, reason):
    monkeypatch.setattr(
        ingest,
        "connect",
        FakeUpstream(close_after_send=True, close_code=code, close_reason=reason),
    )
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()
    return stream_id, exc.value


def test_stream_already_live_closes_with_4423(client, monkeypatch):
    _, closed = closed_by_stream(client, monkeypatch, 1008, "Stream already live")

    assert closed.code == 4423
    assert closed.reason == "Stream already live"


def test_no_data_from_stream_closes_with_1013(client, db_session, monkeypatch):
    stream_id, closed = closed_by_stream(client, monkeypatch, 1013, "No data received")

    assert closed.code == 1013
    assert db_session.get(Stream, stream_id).status == "live"


@pytest.mark.parametrize(
    ("code", "reason"), [(1008, "Stream id already used"), (1012, "")]
)
def test_stream_id_over_ends_the_session(client, db_session, monkeypatch, code, reason):
    stream_id, closed = closed_by_stream(client, monkeypatch, code, reason)

    assert closed.code == 4409
    stream = db_session.get(Stream, stream_id)
    db_session.refresh(stream)
    assert stream.status == "ended"
    assert stream.ended_at is not None


def test_ffmpeg_crash_closes_with_1011(client, monkeypatch):
    _, closed = closed_by_stream(client, monkeypatch, 1011, "Transcoding failed")

    assert closed.code == 1011
    assert closed.reason == "Transcoding failed"


def test_send_failure_closes_with_1011(client, monkeypatch):
    fake = FakeUpstream(send_error=ConnectionClosedError(None, None))
    monkeypatch.setattr(ingest, "connect", fake)
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()

    assert exc.value.code == 1011


def test_first_chunk_marks_the_session_live(client, db_session, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")

    assert db_session.get(Stream, stream_id).status == "live"
    assert db_session.get(Stream, stream_id).started_at is not None


def test_session_stays_created_without_a_chunk(client, db_session, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}"):
        pass

    assert db_session.get(Stream, stream_id).status == "created"


def test_text_frame_closes_with_1003(client, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_text("hello")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()

    assert exc.value.code == 1003


def test_stop_is_passed_on_and_ends_the_session(client, db_session, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")
        ws.close(code=4000)

    assert upstream.sent_close == (4000, "Live ended")
    db_session.expire_all()
    stream = db_session.get(Stream, stream_id)
    assert stream.status == "ended"
    assert stream.ended_at is not None


def test_leaving_without_stop_keeps_the_session_live(client, db_session, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/api/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")
        ws.close(code=1001)

    assert upstream.sent_close is None
    assert db_session.get(Stream, stream_id).status == "live"
