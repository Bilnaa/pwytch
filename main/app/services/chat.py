import asyncio
from urllib.parse import urlencode

from fastapi import WebSocket
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.config import live_chat_settings
from app.models import User
from app.services import auth as auth_service
from app.services import streams as streams_service


class ChatUnavailableError(Exception):
    pass


class BinaryFrameError(Exception):
    pass


def authorize(db: Session, token: str | None, stream_id: int) -> User | None:
    if token is None:
        user = None
    else:
        user = auth_service.get_user_from_token(db, token)
    streams_service.get_stream(db, stream_id)
    return user


def chat_url(stream_id: int, user: User | None) -> str:
    url = f"{live_chat_settings.live_chat_ws_url}/streams/{stream_id}/chat"
    if user is None:
        return url
    return f"{url}?{urlencode({'user_id': user.id, 'username': user.display_name})}"


async def to_chat(websocket: WebSocket, upstream) -> None:
    while True:
        try:
            message = await websocket.receive_text()
        except KeyError as exc:
            raise BinaryFrameError("Only text frames are accepted") from exc
        await upstream.send(message)


async def to_viewer(websocket: WebSocket, upstream) -> None:
    async for message in upstream:
        await websocket.send_text(message)


async def relay(websocket: WebSocket, url: str) -> None:
    try:
        async with connect(
            url, open_timeout=live_chat_settings.live_chat_timeout_seconds
        ) as upstream:
            tasks = {
                asyncio.create_task(to_chat(websocket, upstream)),
                asyncio.create_task(to_viewer(websocket, upstream)),
            }
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.wait(pending)
            for task in done:
                error = task.exception()
                if error is not None:
                    raise error
    except (OSError, TimeoutError, WebSocketException) as exc:
        raise ChatUnavailableError("live-chat is unavailable") from exc


async def run_chat(websocket: WebSocket, db: Session, stream_id: int, user: User | None) -> None:
    url = chat_url(stream_id, user)
    db.close()
    await relay(websocket, url)
