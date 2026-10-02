from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.connection_manager import connectionManager

router = APIRouter(tags=["liveChat"])


@router.websocket("/streams/{stream_id}/chat")
async def live_chat(websocket: WebSocket, stream_id: int):
    await connectionManager.connect(stream_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await connectionManager.broadcast(stream_id, message)
    except WebSocketDisconnect:
        connectionManager.disconnect(stream_id, websocket)