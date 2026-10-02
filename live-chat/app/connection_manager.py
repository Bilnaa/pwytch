from fastapi import WebSocket


class ConnectionManager():
    def __init__(self):
        self.rooms : dict[int, set[WebSocket]] = {}

    async def connect(self, stream_id: int, websocket: WebSocket):
        await websocket.accept()
        if stream_id not in self.rooms:
            self.rooms[stream_id] = set()
        self.rooms[stream_id].add(websocket)
        print(self.rooms)

    def disconnect(self, stream_id: int, websocket: WebSocket):
        room = self.rooms.get(stream_id, set())
        room.discard(websocket)
        if stream_id in self.rooms and len(self.rooms[stream_id]) == 0:
            del self.rooms[stream_id]

    async def broadcast(self, stream_id: int, message: str):
        for ws in list(self.rooms.get(stream_id, set())):
            await ws.send_text(f'{ws} : {message}')



connectionManager = ConnectionManager()