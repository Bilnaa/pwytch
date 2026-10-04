from typing import Annotated

from common.pagination import Page
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_session
from app.infra.repository import find_replay, list_replays
from app.schemas import ReplayResult

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
    items = [ReplayResult.model_validate(replay, from_attributes=True) for replay in replays]
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
