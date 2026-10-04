from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_search_client
from app.schemas.search import StreamerPage
from app.services import search as search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get(
    "/streamers",
    response_model=StreamerPage,
    summary="Search streamers by name, or by title or game of their last live",
    responses={
        502: {"description": "search gave an invalid answer"},
        503: {"description": "search is unavailable"},
        504: {"description": "search took too long to answer"},
    },
)
async def search_streamers(
    client: Annotated[httpx.AsyncClient, Depends(get_search_client)],
    q: Annotated[str, Query(min_length=2, max_length=100)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    try:
        return await search_service.search_streamers(client, q, page, size)
    except search_service.InvalidSearchQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.detail
        ) from exc
    except search_service.InvalidSearchResponseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except search_service.SearchUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except search_service.SearchTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
