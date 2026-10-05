from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import StringConstraints

from app.dependencies import get_search_client
from app.schemas.search import SearchResults
from app.services import search as search_service

router = APIRouter(tags=["search"])

# same bounds as search/app/routers/search.py, keep them aligned
SearchQuery = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


@router.get(
    "/search",
    response_model=SearchResults,
    summary="Search streamers and chat messages of all lives",
)
async def search(
    client: Annotated[httpx.AsyncClient, Depends(get_search_client)],
    q: Annotated[SearchQuery, Query()],
):
    return await search_service.search_all(client, q)
