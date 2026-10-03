from datetime import UTC, datetime
from typing import Annotated

from common.mqtt import MqttClient
from common.pagination import Page
from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query
from pydantic import AfterValidator, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.text import normalize
from app.hits import publish_hits, streamer_hits
from app.infra.db import get_session
from app.infra.repository import search_chat_messages, search_streamers
from app.mqtt import get_mqtt
from app.schemas import MessageResult, StreamerResult

router = APIRouter(prefix="/search", tags=["search"])

# Plus grand INTEGER de Postgres : au-delà, la requête lèverait une erreur (500).
MAX_POSTGRES_INTEGER = 2_147_483_647


def require_searchable_text(search_query: str) -> str:
    # Des diacritiques combinants seuls passent la longueur mais deviennent "" une fois
    # normalisés : la requête correspondrait alors à tout. Le repository normalise déjà.
    if not normalize(search_query):
        raise ValueError("query is empty after normalization")
    # Postgres refuse le caractère nul dans un texte : sans ce contrôle, 500 au lieu de 422.
    if "\x00" in search_query:
        raise ValueError("query contains a null character")
    return search_query


# Le strip passe avant les contrôles de longueur : "   " et " a " donnent 422.
SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
    AfterValidator(require_searchable_text),
]

# Un seul caractère suffit dans le chat : "g", "?" ou un emoji sont des recherches utiles.
ChatSearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(require_searchable_text),
]


@router.get("/streamers")
async def search_streamers_route(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
    mqtt: Annotated[MqttClient, Depends(get_mqtt)],
    background_tasks: BackgroundTasks,
    search_query: Annotated[SearchQuery, Query(alias="q")],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Page[StreamerResult]:
    results, total = await search_streamers(session, search_query, page, size)
    if results:
        hits = streamer_hits(results, search_query, datetime.now(UTC))
        background_tasks.add_task(publish_hits, mqtt, hits)
    return Page[StreamerResult](items=results, total=total, page=page, size=size)


@router.get(
    "/streams/{stream_id}/messages",
    summary="Search the 10 most recent chat messages of a live that contain q",
    responses={422: {"description": "Invalid stream_id or q"}},
)
async def search_chat_messages_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[int, Path(ge=1, le=MAX_POSTGRES_INTEGER)],
    search_query: Annotated[ChatSearchQuery, Query(alias="q")],
) -> list[MessageResult]:
    return await search_chat_messages(session, stream_id, search_query)
