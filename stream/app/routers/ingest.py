import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import settings
from app.hls import HlsError
from app.live import Live, lives

router = APIRouter(tags=["ingest"])


async def refuse(websocket: WebSocket, reason: str) -> None:
    await websocket.accept()
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)


@router.websocket("/streams/{stream_id}/ingest")
async def ingest(stream_id: int, websocket: WebSocket):
    live = lives.get(stream_id)
    if live is None:
        try:
            live = Live.create(stream_id, settings.lives_dir)
        except FileExistsError:
            await refuse(websocket, "Stream id already used")
            return
    elif live.ending:
        await refuse(websocket, "Stream id already used")
        return
    elif live.connected:
        await refuse(websocket, "Stream already live")
        return

    # if the streamer comes back during the grace period, the live goes on in the same playlist
    pipeline = await live.connect()
    try:
        await websocket.accept()
        while True:
            await pipeline.write(await websocket.receive_bytes())
    except WebSocketDisconnect:
        pass
    except HlsError:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Transcoding failed")
    finally:
        await asyncio.shield(live.disconnect(settings.reconnect_seconds))
