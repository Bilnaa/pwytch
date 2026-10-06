from typing import Annotated

import httpx
from common.events import ItemType, TargetType
from fastapi import APIRouter, Depends, Path, Query

from app.dependencies import get_stats_client, require_admin
from app.models import User
from app.schemas.stats import (
    BookmarkDeletedCounterResponse,
    ChatMessageCounterResponse,
    CounterResponse,
    PlayerEventCountersResponse,
)
from app.services import stats as stats_service

router = APIRouter(prefix="/stats", tags=["stats"])

Client = Annotated[httpx.AsyncClient, Depends(get_stats_client)]
Admin = Annotated[User, Depends(require_admin)]

MAX_POSTGRES_INTEGER = 2_147_483_647
Limit = Annotated[int, Query(gt=0, le=500)]
TargetId = Annotated[int, Path(gt=0, le=MAX_POSTGRES_INTEGER)]
StreamId = Annotated[int, Path(gt=0, le=MAX_POSTGRES_INTEGER)]

ERRORS = {
    401: {"description": "Not authenticated"},
    403: {"description": "Admin role required"},
    502: {"description": "stats gave an invalid answer"},
    503: {"description": "stats is unavailable"},
    504: {"description": "stats took too long to answer"},
}


@router.get(
    "/search/top",
    response_model=list[CounterResponse],
    summary="Most found items in the search results, admins only",
    responses=ERRORS,
)
async def get_top_searched(
    client: Client,
    admin: Admin,
    limit: Limit = 10,
    item_type: ItemType | None = None,
):
    return await stats_service.get_top_searched(client, admin, limit, item_type)


@router.get(
    "/search/{item_type}/{item_id}",
    response_model=CounterResponse,
    summary="How many times an item was found by the search, admins only",
    responses=ERRORS,
)
async def get_search_count(client: Client, admin: Admin, item_type: ItemType, item_id: str):
    return await stats_service.get_search_count(client, admin, item_type, item_id)


@router.get(
    "/bookmarks/deleted/top",
    response_model=list[BookmarkDeletedCounterResponse],
    summary="Most removed bookmark targets, admins only",
    responses=ERRORS,
)
async def get_top_bookmark_deleted(
    client: Client,
    admin: Admin,
    limit: Limit = 10,
    target_type: TargetType | None = None,
):
    return await stats_service.get_top_bookmark_deleted(client, admin, limit, target_type)


@router.get(
    "/bookmarks/deleted/{target_type}/{target_id}",
    response_model=BookmarkDeletedCounterResponse,
    summary="How many times a replay or a streamer was removed from the bookmarks, admins only",
    responses=ERRORS,
)
async def get_bookmark_deleted_count(
    client: Client, admin: Admin, target_type: TargetType, target_id: TargetId
):
    return await stats_service.get_bookmark_deleted_count(client, admin, target_type, target_id)


# before /chat/{stream_id}, or "top" would be read as a stream_id and give a 422
@router.get(
    "/chat/top",
    response_model=list[ChatMessageCounterResponse],
    summary="Streams with the most chat messages, admins only",
    responses=ERRORS,
)
async def get_top_chat_messages(client: Client, admin: Admin, limit: Limit = 10):
    return await stats_service.get_top_chat_messages(client, admin, limit)


@router.get(
    "/chat/{stream_id}",
    response_model=ChatMessageCounterResponse,
    summary="How many chat messages were sent in a stream, admins only",
    responses=ERRORS,
)
async def get_chat_message_count(client: Client, admin: Admin, stream_id: StreamId):
    return await stats_service.get_chat_message_count(client, admin, stream_id)


@router.get(
    "/player/{stream_id}",
    response_model=PlayerEventCountersResponse,
    summary="Play, pause and stop counts of a stream, admins only",
    responses=ERRORS,
)
async def get_player_event_counts(client: Client, admin: Admin, stream_id: StreamId):
    return await stats_service.get_player_event_counts(client, admin, stream_id)
