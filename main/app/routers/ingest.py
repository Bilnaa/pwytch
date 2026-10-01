import asyncio
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.config import stream_settings
from app.db import get_db
from app.services import auth as auth_service
from app.services import streams as streams_service

router = APIRouter(tags=["ingest"])

UNAUTHENTICATED = 4401
FORBIDDEN = 4403
NOT_FOUND = 4404
ALREADY_ENDED = 4409
INTERNAL_ERROR = 1011


class StreamUnavailableError(Exception):
    pass


async def forward(websocket: WebSocket, upstream) -> None:
    while True:
        chunk = await websocket.receive_bytes()
        await upstream.send(chunk)


async def relay(websocket: WebSocket, url: str) -> None:
    """Copy the chunks of the streamer to stream until one of the two sides leaves."""
    try:
        async with connect(
            url, max_size=None, open_timeout=stream_settings.stream_timeout_seconds
        ) as upstream:
            forwarding = asyncio.create_task(forward(websocket, upstream))
            upstream_closed = asyncio.create_task(upstream.wait_closed())
            done, _ = await asyncio.wait(
                {forwarding, upstream_closed}, return_when=asyncio.FIRST_COMPLETED
            )
            streamer_left = forwarding in done and isinstance(
                forwarding.exception(), WebSocketDisconnect
            )
            forwarding.cancel()
            upstream_closed.cancel()
            if not streamer_left:
                reason = upstream.close_reason or "stream closed the connection"
                raise StreamUnavailableError(reason)
    except (OSError, TimeoutError, WebSocketException) as exc:
        raise StreamUnavailableError("stream is unavailable") from exc


@router.websocket("/streams/{stream_id}/ingest")
async def ingest(
    websocket: WebSocket,
    stream_id: int,
    token: str,
    db: Annotated[Session, Depends(get_db)],
):
    # a refusal sent before accept() would only be an HTTP 403, the close code would be lost
    await websocket.accept()

    try:
        user = auth_service.get_user_from_token(db, token)
    except auth_service.InvalidCredentialsError:
        await websocket.close(code=UNAUTHENTICATED, reason="Not authenticated")
        return
    try:
        stream = streams_service.get_stream(db, stream_id)
    except streams_service.StreamNotFoundError:
        await websocket.close(code=NOT_FOUND, reason="Stream not found")
        return
    if stream.streamer_id != user.id:
        await websocket.close(code=FORBIDDEN, reason="Not your stream")
        return
    if stream.status in ("ended", "cancelled"):
        await websocket.close(code=ALREADY_ENDED, reason="Stream already ended")
        return

    params = urlencode(
        {
            "streamer_id": user.id,
            "streamer_name": user.display_name,
            "title": stream.title,
            "game": stream.game,
        }
    )
    url = f"{stream_settings.stream_ws_url}/streams/{stream.id}/ingest?{params}"

    # the video lasts hours, don't keep a database connection for all that time
    db.close()

    try:
        await relay(websocket, url)
    except StreamUnavailableError as exc:
        await websocket.close(code=INTERNAL_ERROR, reason=str(exc)[:120])
        return
    await websocket.close()
