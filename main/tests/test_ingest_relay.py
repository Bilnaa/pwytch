import pytest
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError

from app.models import Stream
from app.routers import ingest
from tests.fakes import FakeUpstream, close_code, create_stream


def test_chunks_are_forwarded_unchanged(client, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"\x1a\x45\xdf\xa3")
        ws.send_bytes(b"second chunk")

    assert upstream.chunks == [b"\x1a\x45\xdf\xa3", b"second chunk"]
    assert upstream.exited


def test_stream_receives_the_metadata(client, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}") as ws:
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

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"again")

    assert upstream.chunks == [b"again"]


def test_stream_down_closes_with_1011(client, monkeypatch):
    monkeypatch.setattr(ingest, "connect", FakeUpstream(connect_error=ConnectionRefusedError()))
    stream_id, token = create_stream(client)

    assert close_code(client, f"/streams/{stream_id}/ingest?token={token}") == 1011


def test_stream_closing_the_connection_closes_with_1011(client, monkeypatch):
    fake = FakeUpstream(close_after_send=True)
    monkeypatch.setattr(ingest, "connect", fake)
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()

    assert exc.value.code == 1011
    assert exc.value.reason == "Stream already live"


def test_send_failure_closes_with_1011(client, monkeypatch):
    fake = FakeUpstream(send_error=ConnectionClosedError(None, None))
    monkeypatch.setattr(ingest, "connect", fake)
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()

    assert exc.value.code == 1011


def test_first_chunk_marks_the_session_live(client, db_session, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_bytes(b"x")

    assert db_session.get(Stream, stream_id).status == "live"
    assert db_session.get(Stream, stream_id).started_at is not None


def test_session_stays_created_without_a_chunk(client, db_session, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}"):
        pass

    assert db_session.get(Stream, stream_id).status == "created"


def test_text_frame_closes_with_1003(client, upstream):
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/ingest?token={token}") as ws:
        ws.send_text("hello")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()

    assert exc.value.code == 1003
