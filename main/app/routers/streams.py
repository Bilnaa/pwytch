from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.stream import StreamCreate, StreamPage, StreamResponse, StreamStatus
from app.services import streams as streams_service

router = APIRouter(prefix="/streams", tags=["streams"])


@router.post("", response_model=StreamResponse, status_code=status.HTTP_201_CREATED)
def create_stream(
    payload: StreamCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return streams_service.create_stream(
            db, current_user, payload.title, payload.game
        )
    except streams_service.ActiveStreamExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=StreamPage)
def list_streams(
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[StreamStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    items, total = streams_service.list_streams(db, status_filter, page, size)
    return StreamPage(items=items, total=total, page=page, size=size)


@router.get("/{stream_id}", response_model=StreamResponse)
def get_stream(stream_id: int, db: Annotated[Session, Depends(get_db)]):
    try:
        return streams_service.get_stream(db, stream_id)
    except streams_service.StreamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
