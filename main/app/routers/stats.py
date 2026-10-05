from typing import Annotated

import httpx
from common.events import ItemType
from fastapi import APIRouter, Depends, Query

from app.dependencies import get_stats_client, require_admin
from app.models import User
from app.schemas.stats import CounterResponse
from app.services import stats as stats_service

router = APIRouter(prefix="/stats", tags=["stats"])

Client = Annotated[httpx.AsyncClient, Depends(get_stats_client)]
Admin = Annotated[User, Depends(require_admin)]

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
    limit: Annotated[int, Query(gt=0, le=500)] = 10,
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
