import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from starlette.websockets import WebSocketDisconnect

from app import connection_manager
from app.connection_manager import WAITING_TIME, ConnectionManager, connectionManager
from app.main import app
from app.models.message_model import Author, MessageModel
from app.routers import live_chat

client = TestClient(app)

class FakeSocket:
    def __init__(self):
        self.sent = []
    async def send_text(self, text):
        self.sent.append(text)

class DeadSocket:
    async def send_text(self, text):
        raise WebSocketDisconnect

def test_live_chat_fail_invalid_username():
    with client.websocket_connect("/streams/1/chat?user_id=1&username=%20%20") as ws:
        ws.send_json({"content":"test"})
        reply = ws.receive_json()
        assert reply == {
            "type": "error",
            "code": "READ_ONLY",
            "detail": "Utilisateur non identifié",
        }

def test_live_chat_fail_dead_socket():
    fake_socket = FakeSocket()
    dead_socket = DeadSocket()
    author = Author(id=1, username="user_test")
    message = MessageModel(stream_id=1, author=author, content="test_message")
    manager = ConnectionManager()
    manager.rooms = {1: {fake_socket, dead_socket}}
    asyncio.run(manager.broadcast(1, message))
    assert fake_socket in manager.rooms[1]
    assert fake_socket.sent == [message.model_dump_json()]
    assert dead_socket not in manager.rooms[1]


def test_rate_limit_forgets_expired_entries(monkeypatch):
    now = 100.0
    monkeypatch.setattr(connection_manager.time, "monotonic", lambda: now)
    manager = ConnectionManager()
    assert manager.can_send_message(1, 1)
    assert manager.can_send_message(2, 1)
    assert not manager.can_send_message(1, 1)

    now += WAITING_TIME
    # old entries are removed, so last_sent doesn't grow with every user seen
    assert manager.can_send_message(3, 1)
    assert list(manager.last_sent) == [(3, 1)]
    assert manager.can_send_message(1, 1)

def test_live_chat_saves_then_broadcasts(saved_messages):
    with client.websocket_connect("/streams/1/chat?user_id=1&username=author") as author, \
            client.websocket_connect("/streams/1/chat") as viewer:
        author.send_json({"content": "  hello  "})
        received = viewer.receive_json()
        assert author.receive_json() == received
    assert len(saved_messages) == 1
    saved = saved_messages[0]
    # what is broadcast is exactly what is stored
    assert received == saved.model_dump(mode="json")
    assert saved.content == "hello"
    assert saved.author == Author(id=1, username="author")


def test_live_chat_database_down(database_down, monkeypatch):
    broadcasts = []

    async def spy_broadcast(stream_id, message):
        broadcasts.append(message)

    monkeypatch.setattr(connectionManager, "broadcast", spy_broadcast)
    with client.websocket_connect("/streams/1/chat?user_id=1&username=author") as author:
        author.send_json({"content": "hello"})
        assert author.receive_json() == {
            "type": "error",
            "code": "MESSAGE_NOT_SAVED",
            "detail": "Le message n'a pas pu être enregistré",
        }

        # the WebSocket is still open: the author can keep sending
        author.send_json({"content": ""})
        assert author.receive_json()["code"] == "EMPTY_MESSAGE"

        # a message that wasn't saved doesn't count against the rate limit
        author.send_json({"content": "retry"})
        assert author.receive_json()["code"] == "MESSAGE_NOT_SAVED"
    assert broadcasts == []


def test_live_chat_rate_limited(saved_messages):
    with client.websocket_connect("/streams/1/chat?user_id=1&username=author") as author:
        author.send_json({"content": "first"})
        assert author.receive_json()["content"] == "first"

        # an invalid message doesn't count against the rate limit
        author.send_json({"content": ""})
        assert author.receive_json()["code"] == "EMPTY_MESSAGE"

        author.send_json({"content": "second"})
        assert author.receive_json() == {
            "type": "error",
            "code": "RATE_LIMITED",
            "detail": "Veuillez attendre une seconde.",
        }
    assert [m.content for m in saved_messages] == ["first"]


def test_last_messages_oldest_first(monkeypatch):
    calls = []
    author = Author(id=1, username="author")
    stored = [MessageModel(stream_id=1, author=author, content=c) for c in ("first", "second")]

    async def fake_get(stream_id, limit):
        calls.append((stream_id, limit))
        return stored

    monkeypatch.setattr(live_chat, "get_last_messages", fake_get)
    response = client.get("/streams/1/messages")
    assert response.status_code == 200
    assert [m["content"] for m in response.json()] == ["first", "second"]
    # default limit
    assert calls == [(1, 50)]


def test_last_messages_empty_stream(monkeypatch):
    async def fake_get(stream_id, limit):
        return []

    monkeypatch.setattr(live_chat, "get_last_messages", fake_get)
    response = client.get("/streams/42/messages?limit=1")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("limit", [0, 101, -1, "abc"])
def test_last_messages_invalid_limit(limit):
    assert client.get(f"/streams/1/messages?limit={limit}").status_code == 422


def test_last_messages_database_down(monkeypatch):
    async def failing_get(stream_id, limit):
        raise OperationalError("SELECT", {}, Exception("connection refused"))

    monkeypatch.setattr(live_chat, "get_last_messages", failing_get)
    assert client.get("/streams/1/messages").status_code == 503
