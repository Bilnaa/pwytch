from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Path, Query

from app.dependencies import get_replay_client
from app.schemas.replay import ReplayPage, ReplayResponse
from app.services import replays as replays_service

router = APIRouter(prefix="/replays", tags=["replays"])

MAX_POSTGRES_INTEGER = 2_147_483_647
ReplayId = Annotated[int, Path(ge=1, le=MAX_POSTGRES_INTEGER)]

ERRORS = {
    502: {"description": "replay gave an invalid answer"},
    503: {"description": "replay is unavailable"},
    504: {"description": "replay took too long to answer"},
}


@router.get(
    "",
    response_model=ReplayPage,
    summary="List the replays, from the most recent end",
    responses=ERRORS,
)
async def list_replays(
    client: Annotated[httpx.AsyncClient, Depends(get_replay_client)],
    page: Annotated[int, Query(ge=1, le=MAX_POSTGRES_INTEGER)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
    streamer_id: Annotated[int | None, Query(ge=1, le=MAX_POSTGRES_INTEGER)] = None,
):
    return await replays_service.list_replays(client, page, size, streamer_id)


@router.get(
    "/{stream_id}",
    response_model=ReplayResponse,
    summary="Get one replay",
    responses={404: {"description": "Unknown replay or live still in progress"}, **ERRORS},
)
async def get_replay(
    client: Annotated[httpx.AsyncClient, Depends(get_replay_client)],
    stream_id: ReplayId,
):
    return await replays_service.get_replay(client, stream_id)
