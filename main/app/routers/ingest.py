import asyncio
from collections.abc import Callable
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.config import stream_settings
from app.db import get_db
from app.services import auth as auth_service
from app.models.stream import Status, utcnow
from app.services import streams as streams_service

router = APIRouter(tags=["ingest"])

UNAUTHENTICATED = 4401
FORBIDDEN = 4403
NOT_FOUND = 4404
ALREADY_ENDED = 4409
UNSUPPORTED_DATA = 1003
INTERNAL_ERROR = 1011


class StreamUnavailableError(Exception):
    pass


class TextFrameError(Exception):
    pass


async def forward(websocket: WebSocket, upstream, on_first_chunk: Callable[[], None]) -> None:
    first = True
    while True:
        try:
            chunk = await websocket.receive_bytes()
        except KeyError as exc:
            raise TextFrameError from exc
        await upstream.send(chunk)
        if first:
            first = False
            on_first_chunk()


async def relay(websocket: WebSocket, url: str, on_first_chunk: Callable[[], None]) -> None:
    """Copy the chunks of the streamer to stream until one of the two sides leaves."""
    try:
        async with connect(
            url, max_size=None, open_timeout=stream_settings.stream_timeout_seconds
        ) as upstream:
            forwarding = asyncio.create_task(forward(websocket, upstream, on_first_chunk))
            upstream_closed = asyncio.create_task(upstream.wait_closed())
            done, _ = await asyncio.wait(
                {forwarding, upstream_closed}, return_when=asyncio.FIRST_COMPLETED
            )
            error = forwarding.exception() if forwarding in done else None
            forwarding.cancel()
            upstream_closed.cancel()
            if isinstance(error, TextFrameError):
                raise error
            if not isinstance(error, WebSocketDisconnect):
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
    if stream.status in (Status.ENDED, Status.CANCELLED):
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

    def mark_live() -> None:
        # from the first chunk on, the session is not abandoned anymore
        streams_service.mark_started(db, stream_id, utcnow())
        db.close()

    try:
        await relay(websocket, url, mark_live)
    except TextFrameError:
        await websocket.close(code=UNSUPPORTED_DATA, reason="Only binary frames are accepted")
        return
    except StreamUnavailableError as exc:
        await websocket.close(code=INTERNAL_ERROR, reason=str(exc)[:120])
        return
    await websocket.close()
