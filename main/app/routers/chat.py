from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_chat_user, get_live_chat_client
from app.models import User
from app.schemas.chat import ChatMessage
from app.services import chat as chat_service
from app.services import streams as streams_service

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


@router.get(
    "/streams/{stream_id}/messages",
    response_model=list[ChatMessage],
    summary="Get the last chat messages of a stream, oldest first",
    responses={
        404: {"description": "Unknown stream"},
        502: {"description": "live-chat gave an invalid answer"},
        503: {"description": "live-chat is unavailable"},
        504: {"description": "live-chat took too long to answer"},
    },
)
async def get_messages(
    stream_id: int,
    client: Annotated[httpx.AsyncClient, Depends(get_live_chat_client)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    try:
        return await chat_service.get_messages(client, db, stream_id, limit)
    except streams_service.StreamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
