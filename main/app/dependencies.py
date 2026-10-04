from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, WebSocket, WebSocketException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Stream, User
from app.models.user import ADMIN_ROLE
from app.services import auth as auth_service
from app.services import ingest as ingest_service
from app.services import streams as streams_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

UNAUTHENTICATED = 4401
FORBIDDEN = 4403
NOT_FOUND = 4404
ALREADY_ENDED = 4409


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        return auth_service.get_user_from_token(db, token)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_optional_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if token is None:
        return None
    return get_current_user(token, db)


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )
    return current_user


def get_stream_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.stream_client


def get_search_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.search_client


def get_replay_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.replay_client


def get_stats_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.stats_client


async def get_ingest_stream(
    websocket: WebSocket,
    stream_id: int,
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> Stream:
    # a refusal sent before accept() would only be an HTTP 403, the close code would be lost
    await websocket.accept()
    try:
        return ingest_service.authorize(db, token, stream_id)
    except auth_service.InvalidCredentialsError as exc:
        raise WebSocketException(code=UNAUTHENTICATED, reason="Not authenticated") from exc
    except streams_service.StreamNotFoundError as exc:
        raise WebSocketException(code=NOT_FOUND, reason=str(exc)) from exc
    except ingest_service.NotStreamOwnerError as exc:
        raise WebSocketException(code=FORBIDDEN, reason=str(exc)) from exc
    except ingest_service.StreamOverError as exc:
        raise WebSocketException(code=ALREADY_ENDED, reason=str(exc)) from exc
