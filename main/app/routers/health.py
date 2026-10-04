from typing import Annotated

import httpx
from common.mqtt import MqttClient
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import (
    get_live_chat_client,
    get_mqtt,
    get_replay_client,
    get_search_client,
    get_stats_client,
    get_stream_client,
)
from app.schemas.health import Health
from app.services import health as health_service

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=Health,
    summary="State of the database, the broker and each satellite",
)
async def health(
    db: Annotated[Session, Depends(get_db)],
    mqtt: Annotated[MqttClient, Depends(get_mqtt)],
    stream: Annotated[httpx.AsyncClient, Depends(get_stream_client)],
    search: Annotated[httpx.AsyncClient, Depends(get_search_client)],
    replay: Annotated[httpx.AsyncClient, Depends(get_replay_client)],
    stats: Annotated[httpx.AsyncClient, Depends(get_stats_client)],
    live_chat: Annotated[httpx.AsyncClient, Depends(get_live_chat_client)],
):
    clients = {
        "stream": stream,
        "search": search,
        "replay": replay,
        "stats": stats,
        "live-chat": live_chat,
    }
    return await health_service.check_all(db, mqtt, clients)
