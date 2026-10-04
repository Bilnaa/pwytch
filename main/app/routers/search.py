from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query

from app.dependencies import get_search_client
from app.schemas.search import SearchResults
from app.services import search as search_service

router = APIRouter(tags=["search"])

MAX_STREAM_ID = 2_147_483_647


@router.get(
    "/search",
    response_model=SearchResults,
    summary="Search streamers, and the chat of a live when stream_id is given",
)
async def search(
    client: Annotated[httpx.AsyncClient, Depends(get_search_client)],
    q: Annotated[str, Query(min_length=2, max_length=100)],
    stream_id: Annotated[int | None, Query(ge=1, le=MAX_STREAM_ID)] = None,
):
    return await search_service.search_all(client, q, stream_id)
