import asyncio
import logging

import httpx
from common.pagination import Page
from pydantic import TypeAdapter, ValidationError

from app.schemas.search import MessageResult, SearchResults, StreamerResult

logger = logging.getLogger(__name__)

STREAMER_PAGE = TypeAdapter(Page[StreamerResult])
MESSAGE_LIST = TypeAdapter(list[MessageResult])


class SearchSectionError(Exception):
    pass


async def _get(client: httpx.AsyncClient, path: str, query: str, adapter: TypeAdapter):
    try:
        response = await client.get(path, params={"q": query})
    except httpx.TimeoutException as exc:
        raise SearchSectionError("search timed out") from exc
    except httpx.HTTPError as exc:
        raise SearchSectionError("search is unavailable") from exc

    if response.status_code != 200:
        raise SearchSectionError(f"search answered {response.status_code}")
    try:
        return adapter.validate_json(response.content)
    except ValidationError as exc:
        raise SearchSectionError("Invalid answer from search") from exc


async def search_streamers(client: httpx.AsyncClient, query: str) -> list[StreamerResult]:
    page = await _get(client, "/search/streamers", query, STREAMER_PAGE)
    return page.items


async def search_messages(
    client: httpx.AsyncClient, query: str, stream_id: int | None
) -> list[MessageResult]:
    if stream_id is None:
        return []
    return await _get(client, f"/search/streams/{stream_id}/messages", query, MESSAGE_LIST)


async def _or_empty(section: str, search) -> list:
    try:
        return await search
    except SearchSectionError as exc:
        logger.warning("Search section %s left empty: %s", section, exc)
        return []


async def search_all(
    client: httpx.AsyncClient, query: str, stream_id: int | None
) -> SearchResults:
    streamers, messages = await asyncio.gather(
        _or_empty("streamers", search_streamers(client, query)),
        _or_empty("messages", search_messages(client, query, stream_id)),
    )
    return SearchResults(streamers=streamers, messages=messages)
