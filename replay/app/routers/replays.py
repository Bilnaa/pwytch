from typing import Annotated

from common.pagination import Page
from fastapi import APIRouter, BackgroundTasks, Path, Query
from fastapi.responses import FileResponse, JSONResponse

from app.dependencies import ConverterDep, SessionDep
from app.helpers.constants import MAX_POSTGRES_INTEGER, RETRY_AFTER_SECONDS
from app.schemas import ConversionPending, ReplayResult
from app.services import replay_service
from app.services.replay_service import Mp4Ready

router = APIRouter(prefix="/replays", tags=["replays"])

ReplayId = Annotated[int, Path(ge=1, le=MAX_POSTGRES_INTEGER)]


@router.get("", summary="List the replays, from the most recent end")
async def list_replays_route(
    session: SessionDep,
    # Borné comme les ids : une page énorme ferait dépasser l'OFFSET des entiers 64 bits (500).
    page: Annotated[int, Query(ge=1, le=MAX_POSTGRES_INTEGER)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
    streamer_id: Annotated[int | None, Query(ge=1, le=MAX_POSTGRES_INTEGER)] = None,
) -> Page[ReplayResult]:
    return await replay_service.list_replays_page(session, page, size, streamer_id)


@router.get(
    "/{stream_id}",
    summary="Get one replay",
    responses={404: {"description": "Unknown replay or live still in progress"}},
)
async def get_replay_route(session: SessionDep, stream_id: ReplayId) -> ReplayResult:
    return await replay_service.get_replay(session, stream_id)


@router.get(
    "/{stream_id}/video",
    summary="Play the replay mp4 in the browser, with Range requests to seek",
    response_class=FileResponse,
    responses={
        200: {"description": "The whole mp4", "content": {"video/mp4": {}}},
        206: {"description": "The part asked by the Range header", "content": {"video/mp4": {}}},
        404: {"description": "Unknown replay, live still in progress or mp4 not ready"},
    },
)
async def replay_video_route(session: SessionDep, converter: ConverterDep, stream_id: ReplayId):
    mp4_path = await replay_service.video_path(session, converter, stream_id)
    # Sans filename : servi inline, FileResponse répond aux en-têtes Range par un 206.
    return FileResponse(mp4_path, media_type="video/mp4")


@router.get(
    "/{stream_id}/download",
    summary="Download the replay as mp4, converted on the first request",
    response_class=FileResponse,
    responses={
        200: {
            "description": "The mp4 file, as an attachment",
            "content": {"video/mp4": {}},
        },
        202: {
            "description": "Conversion in progress, retry later",
            "model": ConversionPending,
        },
        404: {"description": "Unknown replay or live still in progress"},
        500: {"description": "Conversion failed; the next request starts it again"},
    },
)
async def download_replay_route(
    session: SessionDep,
    converter: ConverterDep,
    background_tasks: BackgroundTasks,
    stream_id: ReplayId,
):
    result = await replay_service.prepare_download(
        session, converter, background_tasks.add_task, stream_id
    )
    if isinstance(result, Mp4Ready):
        return FileResponse(result.path, media_type="video/mp4", filename=result.filename)
    # FastAPI rattache background_tasks à une Response renvoyée directement.
    return JSONResponse(
        status_code=202,
        content=result.model_dump(mode="json"),
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )
