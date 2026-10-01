from fastapi import APIRouter, WebSocket
from app.connection_manager import connectionManager

router = APIRouter(tags=["liveChat"])


@router.websocket("/streams/{stream_id}/chat")
async def live_chat(websocket: WebSocket, stream_id: int, user_id: int | None = None, username: str | None = None):
    await connectionManager.connect(stream_id, websocket)
    while True:
        message = await websocket.receive_text()
        await connectionManager.broadcast(stream_id, message)