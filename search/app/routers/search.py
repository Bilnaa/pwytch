from typing import Annotated

from common.pagination import Page
from fastapi import APIRouter, Depends, Query
from pydantic import AfterValidator, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.text import normalize
from app.infra.db import get_session
from app.infra.repository import search_streamers
from app.schemas import StreamerResult

router = APIRouter(prefix="/search", tags=["search"])


def require_searchable_text(search_query: str) -> str:
    # Des diacritiques combinants seuls passent la longueur mais deviennent "" une fois
    # normalisés : la requête correspondrait alors à tout. Le repository normalise déjà.
    if not normalize(search_query):
        raise ValueError("query is empty after normalization")
    return search_query


# Le strip passe avant les contrôles de longueur : "   " et " a " donnent 422.
SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
    AfterValidator(require_searchable_text),
]


@router.get("/streamers")
async def search_streamers_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    search_query: Annotated[SearchQuery, Query(alias="q")],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Page[StreamerResult]:
    results, total = await search_streamers(session, search_query, page, size)
    return Page[StreamerResult](items=results, total=total, page=page, size=size)
