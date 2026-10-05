from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.dependencies import get_replay_client
from app.schemas.replay import ConversionPending, ReplayPage, ReplayResponse
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


@router.get(
    "/{stream_id}/download",
    summary="Relay the mp4 of a replay, converted by replay on the first request",
    response_class=StreamingResponse,
    responses={
        200: {"description": "The mp4 file, as an attachment", "content": {"video/mp4": {}}},
        202: {"description": "Conversion in progress, retry later", "model": ConversionPending},
        404: {"description": "Unknown replay or live still in progress"},
        **ERRORS,
    },
)
async def download_replay(
    client: Annotated[httpx.AsyncClient, Depends(get_replay_client)],
    stream_id: ReplayId,
):
    download = await replays_service.open_replay_download(client, stream_id)
    return StreamingResponse(
        download.content,
        status_code=download.status_code,
        media_type=download.media_type,
        headers=download.headers,
        background=BackgroundTask(download.close),
    )
