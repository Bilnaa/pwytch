import asyncio

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.connection_manager import ConnectionManager
from app.models.message_model import MessageModel, Author

from app.main import app

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
        assert reply == {"type": "error", "code": "READ_ONLY", "detail": "Utilisateur non identifié"}

def test_live_chat_fail_dead_socket():
    fake_socket = FakeSocket()
    dead_socket = DeadSocket()
    message = MessageModel(stream_id=1, author=Author(id=1, username="user_test"), content="test_message")
    manager = ConnectionManager()
    manager.rooms = {1: {fake_socket, dead_socket}}
    asyncio.run(manager.broadcast(1, message))
    assert fake_socket in manager.rooms[1]
    assert fake_socket.sent == [message.model_dump_json()]
    assert dead_socket not in manager.rooms[1]
