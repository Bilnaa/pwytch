import asyncio
import logging

import httpx
from common.pagination import Page
from pydantic import TypeAdapter

from app.schemas.search import MessageResult, SearchResults, StreamerResult
from app.services import satellites

logger = logging.getLogger(__name__)

STREAMER_PAGE = TypeAdapter(Page[StreamerResult])
MESSAGE_LIST = TypeAdapter(list[MessageResult])


async def _get(client: httpx.AsyncClient, path: str, query: str, adapter: TypeAdapter):
    response = await satellites.send(client, "GET", path, params={"q": query})
    return satellites.parse(response, adapter)


async def search_streamers(client: httpx.AsyncClient, query: str) -> list[StreamerResult]:
    page = await _get(client, "/search/streamers", query, STREAMER_PAGE)
    return page.items


async def search_messages(client: httpx.AsyncClient, query: str) -> list[MessageResult]:
    return await _get(client, "/search/messages", query, MESSAGE_LIST)


async def _or_empty(section: str, search) -> list:
    try:
        return await search
    except satellites.SatelliteError as exc:
        logger.warning("Search section %s left empty: %s", section, exc)
        return []


async def search_all(client: httpx.AsyncClient, query: str) -> SearchResults:
    streamers, messages = await asyncio.gather(
        _or_empty("streamers", search_streamers(client, query)),
        _or_empty("messages", search_messages(client, query)),
    )
    return SearchResults(streamers=streamers, messages=messages)
