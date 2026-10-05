from typing import Annotated

from common.pagination import Page
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversion import Mp4Converter, get_converter
from app.infra.db import get_session
from app.infra.models import Mp4Status
from app.infra.repository import (
    claim_conversion,
    find_replay,
    list_replays,
    set_mp4_status,
)
from app.schemas import ConversionPending, ReplayResult

router = APIRouter(prefix="/replays", tags=["replays"])

# Plus grand INTEGER de Postgres : au-delà, la requête lèverait une erreur (500).
MAX_POSTGRES_INTEGER = 2_147_483_647

ReplayId = Annotated[int, Path(ge=1, le=MAX_POSTGRES_INTEGER)]
# Session rendue dès la fin de la route, avant les éventuelles tâches de fond.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


@router.get("", summary="List the replays, from the most recent end")
async def list_replays_route(
    session: SessionDep,
    # Borné comme les ids : une page énorme ferait dépasser l'OFFSET des entiers 64 bits (500).
    page: Annotated[int, Query(ge=1, le=MAX_POSTGRES_INTEGER)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
    streamer_id: Annotated[int | None, Query(ge=1, le=MAX_POSTGRES_INTEGER)] = None,
) -> Page[ReplayResult]:
    replays, total = await list_replays(session, page, size, streamer_id)
    items = [
        ReplayResult.model_validate(replay, from_attributes=True) for replay in replays
    ]
    return Page[ReplayResult](items=items, total=total, page=page, size=size)


@router.get(
    "/{stream_id}",
    summary="Get one replay",
    responses={404: {"description": "Unknown replay or live still in progress"}},
)
async def get_replay_route(session: SessionDep, stream_id: ReplayId) -> ReplayResult:
    replay = await find_replay(session, stream_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Replay not found")
    return ReplayResult.model_validate(replay, from_attributes=True)


# Délai conseillé au client avant de redemander le fichier.
RETRY_AFTER_SECONDS = 5


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
    converter: Annotated[Mp4Converter, Depends(get_converter)],
    background_tasks: BackgroundTasks,
    stream_id: ReplayId,
):
    replay = await find_replay(session, stream_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Replay not found")

    mp4_status = replay.mp4_status
    if mp4_status is Mp4Status.READY:
        mp4_path = converter.mp4_path(stream_id)
        if mp4_path.is_file():
            return FileResponse(
                mp4_path, media_type="video/mp4", filename=f"replay-{stream_id}.mp4"
            )
        # Fichier supprimé ou volume perdu, on relance la conversion.
        await set_mp4_status(session, stream_id, Mp4Status.NONE)
        mp4_status = Mp4Status.NONE

    if mp4_status is Mp4Status.FAILED:
        # L'échec est signalé une fois, la demande suivante relance ffmpeg.
        await set_mp4_status(session, stream_id, Mp4Status.NONE)
        raise HTTPException(status_code=500, detail="Conversion failed, try again")

    if mp4_status is Mp4Status.NONE and await claim_conversion(session, stream_id):
        # Lancée après l'envoi de la réponse, avec ses propres sessions.
        background_tasks.add_task(converter.convert, stream_id)

    # FastAPI rattache background_tasks à une Response renvoyée directement.
    return JSONResponse(
        status_code=202,
        content=ConversionPending(stream_id=stream_id).model_dump(mode="json"),
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )
