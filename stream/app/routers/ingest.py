from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import settings
from app.hls import HlsError, HlsPipeline

router = APIRouter(tags=["ingest"])

active_streams: dict[int, HlsPipeline] = {}


@router.websocket("/streams/{stream_id}/ingest")
async def ingest(stream_id: int, websocket: WebSocket):
    if stream_id in active_streams:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Stream already live")
        return

    pipeline = HlsPipeline(stream_id, settings.lives_dir)
    try:
        await pipeline.start()
    except FileExistsError:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Stream id already used")
        return
    active_streams[stream_id] = pipeline
    try:
        await websocket.accept()
        while True:
            await pipeline.write(await websocket.receive_bytes())
    except WebSocketDisconnect:
        pass
    except HlsError:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Transcoding failed")
    finally:
        try:
            await pipeline.close()
        finally:
            # may run before ffmpeg is done (abrupt disconnect), the folder still blocks a reconnect
            active_streams.pop(stream_id, None)
