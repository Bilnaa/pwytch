from typing import Annotated

from common.mqtt import MqttClient
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user, get_mqtt, get_optional_user
from app.models import User
from app.schemas.stream import (
    PlayerEventCreate,
    StreamCreate,
    StreamPage,
    StreamResponse,
    StreamStatus,
)
from app.services import player_events as player_events_service
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


@router.post(
    "/{stream_id}/player-events",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    summary="Count a play, pause or stop of the player in the stats",
    responses={
        202: {"description": "Accepted, published on player/event afterwards"},
        404: {"description": "Stream not found"},
        429: {"description": "Too many events from this client for this stream"},
    },
)
def create_player_event(
    stream_id: int,
    payload: PlayerEventCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User | None, Depends(get_optional_user)],
    mqtt: Annotated[MqttClient, Depends(get_mqtt)],
    db: Annotated[Session, Depends(get_db)],
):
    client = request.client.host if request.client else "unknown"
    try:
        event = player_events_service.create_player_event(
            db, client, stream_id, payload.event_type, current_user
        )
    except player_events_service.TooManyPlayerEventsError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
    except streams_service.StreamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    background_tasks.add_task(player_events_service.publish_player_event, mqtt, event)
    return Response(status_code=status.HTTP_202_ACCEPTED)
