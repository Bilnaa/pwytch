import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError

from app.models import Stream
from app.routers import ingest
from tests.test_streams_router import PAYLOAD, auth_headers


class FakeUpstream:
    """Stands for the WebSocket of stream, so the tests don't need the real service."""

    def __init__(self, close_after_send=False, send_error=None, connect_error=None):
        self.chunks = []
        self.urls = []
        self.close_reason = ""
        self.close_after_send = close_after_send
        self.send_error = send_error
        self.connect_error = connect_error
        self.entered = False
        self.exited = False
        self._closed = None

    def __call__(self, url, **kwargs):
        self.urls.append(url)
        return self

    async def __aenter__(self):
        if self.connect_error:
            raise self.connect_error
        self._closed = asyncio.Event()
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        self.exited = True

    async def send(self, chunk):
        if self.send_error:
            raise self.send_error
        self.chunks.append(chunk)
        if self.close_after_send:
            self.close_reason = "Stream already live"
            self._closed.set()

    async def wait_closed(self):
        await self._closed.wait()


@pytest.fixture
def upstream(monkeypatch):
    fake = FakeUpstream()
    monkeypatch.setattr(ingest, "connect", fake)
    return fake


def create_stream(client, username="alice"):
    headers = auth_headers(client, username)
    response = client.post("/streams", json=PAYLOAD, headers=headers)
    return response.json()["id"], headers["Authorization"].removeprefix("Bearer ")


def close_code(client, path):
    with client.websocket_connect(path) as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()
    return exc.value.code


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


def test_missing_or_bad_token_closes_with_4401(client, upstream):
    stream_id, _ = create_stream(client)

    assert close_code(client, f"/streams/{stream_id}/ingest?token=nope") == 4401
    assert upstream.urls == []


def test_missing_token_is_rejected(client, upstream):
    stream_id, _ = create_stream(client)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/streams/{stream_id}/ingest"):
            pass


def test_other_streamer_closes_with_4403(client, upstream):
    stream_id, _ = create_stream(client, "alice")
    _, bob_token = create_stream(client, "bob")

    assert close_code(client, f"/streams/{stream_id}/ingest?token={bob_token}") == 4403
    assert upstream.urls == []


def test_unknown_stream_closes_with_4404(client, upstream):
    _, token = create_stream(client)

    assert close_code(client, f"/streams/999/ingest?token={token}") == 4404


@pytest.mark.parametrize("status", ["ended", "cancelled"])
def test_finished_stream_closes_with_4409(client, db_session, upstream, status):
    stream_id, token = create_stream(client)
    db_session.get(Stream, stream_id).status = status
    db_session.commit()

    assert close_code(client, f"/streams/{stream_id}/ingest?token={token}") == 4409
    assert upstream.urls == []


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
