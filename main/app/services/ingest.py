import asyncio
from collections.abc import Callable
from urllib.parse import urlencode

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.config import stream_settings
from app.models import Stream
from app.models.stream import Status, utcnow
from app.services import auth as auth_service
from app.services import streams as streams_service

STREAM_REFUSED = 1008
STREAM_RESTARTING = 1012
STREAM_NO_DATA = 1013
STREAM_ALREADY_LIVE = "Stream already live"
STREAM_ID_USED = "Stream id already used"
# sent by the front when the streamer clicks Stop, passed on to stream as is.
# Any other close is a cut: stream waits for the streamer to come back
LIVE_ENDED = 4000


class NotStreamOwnerError(Exception):
    pass


class StreamOverError(Exception):
    pass


class StreamAlreadyLiveError(Exception):
    pass


class SignalLostError(Exception):
    pass


class StreamUnavailableError(Exception):
    pass


class TextFrameError(Exception):
    pass


class UpstreamClosedError(Exception):
    def __init__(self, code: int | None, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def authorize(db: Session, token: str, stream_id: int) -> Stream:
    user = auth_service.get_user_from_token(db, token)
    stream = streams_service.get_stream(db, stream_id)
    if stream.streamer_id != user.id:
        raise NotStreamOwnerError("Not your stream")
    if stream.status in (Status.ENDED, Status.CANCELLED):
        raise StreamOverError("Stream already ended")
    return stream


def stream_url(stream: Stream) -> str:
    params = urlencode(
        {
            "streamer_id": stream.streamer.id,
            "streamer_name": stream.streamer.display_name,
            "title": stream.title,
            "game": stream.game,
        }
    )
    return f"{stream_settings.stream_ws_url}/streams/{stream.id}/ingest?{params}"


async def forward(websocket: WebSocket, upstream, on_first_chunk: Callable[[], None]) -> None:
    first = True
    while True:
        try:
            chunk = await websocket.receive_bytes()
        except KeyError as exc:
            raise TextFrameError("Only binary frames are accepted") from exc
        await upstream.send(chunk)
        if first:
            first = False
            on_first_chunk()


async def relay(websocket: WebSocket, url: str, on_first_chunk: Callable[[], None]) -> bool:
    """Copy the chunks of the streamer to stream until one of the two sides leaves.

    Returns True when the streamer ended the live (Stop), False when they left."""
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
                raise UpstreamClosedError(upstream.close_code, reason)
            if error.code == LIVE_ENDED:
                await upstream.close(LIVE_ENDED, "Live ended")
                return True
            return False
    except (OSError, TimeoutError, WebSocketException) as exc:
        raise StreamUnavailableError("stream is unavailable") from exc


def session_is_over(exc: UpstreamClosedError) -> bool:
    if exc.code == STREAM_RESTARTING:
        return True
    return exc.code == STREAM_REFUSED and exc.reason == STREAM_ID_USED


async def run_ingest(websocket: WebSocket, db: Session, stream: Stream) -> None:
    url = stream_url(stream)
    stream_id = stream.id

    # the video lasts hours, don't keep a database connection for all that time
    db.close()

    def mark_live() -> None:
        # from the first chunk on, the session is not abandoned anymore
        streams_service.mark_started(db, stream_id, utcnow())
        db.close()

    def mark_over() -> None:
        streams_service.mark_over(db, stream_id, utcnow())
        db.close()

    try:
        stopped = await relay(websocket, url, mark_live)
    except UpstreamClosedError as exc:
        if session_is_over(exc):
            await asyncio.to_thread(mark_over)
            raise StreamOverError("Stream already ended") from exc
        if exc.code == STREAM_NO_DATA:
            raise SignalLostError(exc.reason) from exc
        if exc.code == STREAM_REFUSED and exc.reason == STREAM_ALREADY_LIVE:
            raise StreamAlreadyLiveError(exc.reason) from exc
        raise StreamUnavailableError(exc.reason) from exc
    if stopped:
        # no need to wait for stream/ended: the streamer can go live again right away
        await asyncio.to_thread(mark_over)
