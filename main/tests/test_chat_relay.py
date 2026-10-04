import pytest
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError

from app.services import chat
from tests.fakes import FakeChat, close_code, create_stream


def test_bad_token_closes_with_4401(client, live_chat):
    stream_id, _ = create_stream(client)

    assert close_code(client, f"/streams/{stream_id}/chat?token=nope") == 4401
    assert live_chat.urls == []


def test_unknown_stream_closes_with_4404(client, live_chat):
    _, token = create_stream(client)

    assert close_code(client, f"/streams/999/chat?token={token}") == 4404
    assert live_chat.urls == []


def test_unknown_stream_without_token_closes_with_4404(client, live_chat):
    assert close_code(client, "/streams/999/chat") == 4404


def test_viewer_without_token_is_anonymous(client, live_chat):
    stream_id, _ = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/chat"):
        pass

    assert live_chat.urls == [f"ws://localhost:8002/streams/{stream_id}/chat"]


def test_viewer_with_token_is_identified(client, live_chat):
    stream_id, _ = create_stream(client)
    _, token = create_stream(client, "Bob")

    with client.websocket_connect(f"/streams/{stream_id}/chat?token={token}"):
        pass

    url = live_chat.urls[0]
    assert url.startswith(f"ws://localhost:8002/streams/{stream_id}/chat?")
    assert "user_id=" in url
    assert "username=Bob" in url


def test_messages_are_relayed_both_ways(client, monkeypatch):
    fake = FakeChat(messages=['{"content": "hi"}'])
    monkeypatch.setattr(chat, "connect", fake)
    stream_id, token = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/chat?token={token}") as ws:
        assert ws.receive_text() == '{"content": "hi"}'
        ws.send_text('{"content": "hello"}')

    assert fake.sent == ['{"content": "hello"}']


def test_viewer_leaving_closes_live_chat(client, live_chat):
    stream_id, _ = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/chat"):
        pass

    assert live_chat.exited


def test_live_chat_closing_closes_the_viewer(client, monkeypatch):
    monkeypatch.setattr(chat, "connect", FakeChat(close_after_send=True))
    stream_id, _ = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/chat") as ws:
        ws.send_text("x")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()

    assert exc.value.code == 1000


def test_live_chat_down_closes_with_1011(client, monkeypatch):
    monkeypatch.setattr(chat, "connect", FakeChat(connect_error=ConnectionRefusedError()))
    stream_id, _ = create_stream(client)

    assert close_code(client, f"/streams/{stream_id}/chat") == 1011


def test_live_chat_crash_closes_with_1011(client, monkeypatch):
    fake = FakeChat(close_after_send=True, close_error=ConnectionClosedError(None, None))
    monkeypatch.setattr(chat, "connect", fake)
    stream_id, _ = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/chat") as ws:
        ws.send_text("x")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()

    assert exc.value.code == 1011


def test_binary_frame_closes_with_1003(client, live_chat):
    stream_id, _ = create_stream(client)

    with client.websocket_connect(f"/streams/{stream_id}/chat") as ws:
        ws.send_bytes(b"x")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()

    assert exc.value.code == 1003
