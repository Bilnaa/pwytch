from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_chat_user
from app.models import User
from app.services import chat as chat_service

router = APIRouter(tags=["chat"])

UNSUPPORTED_DATA = 1003
INTERNAL_ERROR = 1011


@router.websocket("/streams/{stream_id}/chat")
async def chat(
    websocket: WebSocket,
    stream_id: int,
    user: Annotated[User | None, Depends(get_chat_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        await chat_service.run_chat(websocket, db, stream_id, user)
    except WebSocketDisconnect:
        pass
    except chat_service.BinaryFrameError as exc:
        await websocket.close(code=UNSUPPORTED_DATA, reason=str(exc))
    except chat_service.ChatUnavailableError as exc:
        await websocket.close(code=INTERNAL_ERROR, reason=str(exc))
    else:
        await websocket.close()
