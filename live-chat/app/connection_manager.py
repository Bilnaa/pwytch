import time
from collections import OrderedDict

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.models.message_model import MessageModel

WAITING_TIME = 1

class ConnectionManager:
    def __init__(self):
        self.rooms : dict[int, set[WebSocket]] = {}
        # A dict of the user, the stream_id associated with it and the time
        # the last message associated to it was sent
        # Float is for a time value
        # Entries are in sending order, so expired ones are always at the front
        self.last_sent : OrderedDict[tuple[int, int], float] = OrderedDict()

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
        self.forget_expired(now)
        # Every entry left was sent less than WAITING_TIME ago
        if (user_id, stream_id) in self.last_sent:
            return False
        self.last_sent[(user_id, stream_id)] = now
        return True

    def forget_expired(self, now: float) -> None:
        # Without this, last_sent would grow with every (user, stream) couple
        # ever seen, and user_id comes from the URL
        while self.last_sent:
            key, sent_at = next(iter(self.last_sent.items()))
            if now - sent_at < WAITING_TIME:
                break
            del self.last_sent[key]

    def cancel_last_message(self, user_id: int, stream_id: int) -> None:
        # Gives the slot back when the message couldn't be saved, so a retry
        # isn't rate limited. The slot stays reserved during the save so that
        # two sockets of the same user can't both send at the same time
        self.last_sent.pop((user_id, stream_id), None)


connectionManager = ConnectionManager()