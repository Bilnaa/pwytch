import asyncio

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.connection_manager import ConnectionManager, connectionManager
from app.main import app
from app.models.message_model import Author, MessageModel

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
    assert broadcasts == []
