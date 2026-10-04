from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
import time

from app.models.message_model import MessageModel

WAITING_TIME = 1

class ConnectionManager:
    def __init__(self):
        self.rooms : dict[int, set[WebSocket]] = {}
        # A dict of the user, the stream_id associated with it and the time
        # the last message associated to it was sent
        # Float is for a time value
        self.last_sent : dict[tuple[int, int], float] = {}

    async def connect(self, stream_id: int, websocket: WebSocket):
        await websocket.accept()
        if stream_id not in self.rooms:
            self.rooms[stream_id] = set()
        self.rooms[stream_id].add(websocket)

    def disconnect(self, stream_id: int, websocket: WebSocket):
        room = self.rooms.get(stream_id, set())
        room.discard(websocket)
        if stream_id in self.rooms and len(self.rooms[stream_id]) == 0:
            del self.rooms[stream_id]

    async def broadcast(self, stream_id: int, message: MessageModel):
        payload = message.model_dump_json()
        for ws in list(self.rooms.get(stream_id, set())):
            try:
                await ws.send_text(payload)
            except (WebSocketDisconnect, RuntimeError):
                self.disconnect(stream_id, ws)

    def can_send_message(self, user_id: int, stream_id: int) -> bool:
        now = time.monotonic()
        author_last_message = self.last_sent.get((user_id, stream_id))
        if author_last_message is not None and now - author_last_message < WAITING_TIME:
            return False
        self.last_sent[(user_id, stream_id)] = now
        return True


connectionManager = ConnectionManager()