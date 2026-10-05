from typing import Annotated

from common.pagination import Page
from fastapi import APIRouter, Path, Query

from app.dependencies import HitPublisherDep, SessionDep
from app.helpers.constants import MAX_POSTGRES_INTEGER
from app.schemas import MessageResult, StreamerResult
from app.schemas.search_query import ChatSearchQuery, SearchQuery
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/streamers")
async def search_streamers_route(
    session: SessionDep,
    hits: HitPublisherDep,
    search_query: Annotated[SearchQuery, Query(alias="q")],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Page[StreamerResult]:
    return await search_service.search_streamers(session, hits, search_query, page, size)


@router.get(
    "/streams/{stream_id}/messages",
    summary="Search the 10 most recent chat messages of a live that contain q",
    responses={422: {"description": "Invalid stream_id or q"}},
)
async def search_chat_messages_route(
    session: SessionDep,
    hits: HitPublisherDep,
    stream_id: Annotated[int, Path(ge=1, le=MAX_POSTGRES_INTEGER)],
    search_query: Annotated[ChatSearchQuery, Query(alias="q")],
) -> list[MessageResult]:
    return await search_service.search_chat_messages(session, hits, stream_id, search_query)


@router.get(
    "/messages",
    summary="Search the 10 most recent chat messages of every live that contain q",
    responses={422: {"description": "Invalid q"}},
)
async def search_all_chat_messages_route(
    session: SessionDep,
    hits: HitPublisherDep,
    search_query: Annotated[SearchQuery, Query(alias="q")],
) -> list[MessageResult]:
    return await search_service.search_all_chat_messages(session, hits, search_query)
