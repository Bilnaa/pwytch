import asyncio

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from starlette.requests import ClientDisconnect

from app.config import settings
from app.hls import HlsError
from app.live import Live, lives

router = APIRouter(tags=["ingest"])


class Refused(Exception):
    pass


def get_live(stream_id: int) -> Live:
    live = lives.get(stream_id)
    if live is None:
        try:
            return Live.create(stream_id, settings.lives_dir)
        except FileExistsError:
            raise Refused("Stream id already used")
    if live.ending:
        raise Refused("Stream id already used")
    if live.connected:
        raise Refused("Stream already live")
    # the streamer comes back during the grace period, the live goes on in the same playlist
    return live


@router.websocket("/streams/{stream_id}/ingest")
async def ingest(stream_id: int, websocket: WebSocket):
    try:
        live = get_live(stream_id)
    except Refused as exc:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc))
        return

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


# dev only: same live and same ffmpeg as the WebSocket, main never exposes it
@router.post(
    "/streams/{stream_id}/ingest",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Send a video over HTTP instead of the WebSocket (dev only)",
    responses={409: {"description": "Stream already live or stream id already used"}},
)
async def ingest_http(stream_id: int, request: Request):
    try:
        live = get_live(stream_id)
    except Refused as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    pipeline = await live.connect()
    try:
        async for chunk in request.stream():
            if chunk:
                await pipeline.write(chunk)
    except ClientDisconnect:
        pass
    except HlsError:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Transcoding failed")
    finally:
        await asyncio.shield(live.disconnect(settings.reconnect_seconds))
