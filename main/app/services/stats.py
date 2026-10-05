import httpx
from common.events import ItemType, TargetType
from pydantic import TypeAdapter

from app.models import User
from app.schemas.stats import (
    BookmarkDeletedCounterResponse,
    ChatMessageCounterResponse,
    CounterResponse,
    PlayerEventCountersResponse,
)
from app.services import satellites

COUNTER = TypeAdapter(CounterResponse)
COUNTER_LIST = TypeAdapter(list[CounterResponse])
BOOKMARK_DELETED = TypeAdapter(BookmarkDeletedCounterResponse)
BOOKMARK_DELETED_LIST = TypeAdapter(list[BookmarkDeletedCounterResponse])
CHAT_MESSAGES = TypeAdapter(ChatMessageCounterResponse)
CHAT_MESSAGES_LIST = TypeAdapter(list[ChatMessageCounterResponse])
PLAYER_EVENTS = TypeAdapter(PlayerEventCountersResponse)


async def get_search_count(
    client: httpx.AsyncClient, user: User, item_type: ItemType, item_id: str
) -> CounterResponse:
    response = await satellites.send(
        client, "GET", f"/stats/search/{item_type}/{item_id}", user=user
    )
    return satellites.parse(response, COUNTER)


async def get_top_searched(
    client: httpx.AsyncClient, user: User, limit: int, item_type: ItemType | None
) -> list[CounterResponse]:
    params = {"limit": limit}
    if item_type is not None:
        params["item_type"] = item_type
    response = await satellites.send(
        client, "GET", "/stats/search/top", user=user, params=params
    )
    return satellites.parse(response, COUNTER_LIST)


async def get_bookmark_deleted_count(
    client: httpx.AsyncClient, user: User, target_type: TargetType, target_id: int
) -> BookmarkDeletedCounterResponse:
    response = await satellites.send(
        client, "GET", f"/stats/bookmarks/deleted/{target_type}/{target_id}", user=user
    )
    return satellites.parse(response, BOOKMARK_DELETED)


async def get_top_bookmark_deleted(
    client: httpx.AsyncClient, user: User, limit: int, target_type: TargetType | None
) -> list[BookmarkDeletedCounterResponse]:
    params = {"limit": limit}
    if target_type is not None:
        params["target_type"] = target_type
    response = await satellites.send(
        client, "GET", "/stats/bookmarks/deleted/top", user=user, params=params
    )
    return satellites.parse(response, BOOKMARK_DELETED_LIST)


async def get_chat_message_count(
    client: httpx.AsyncClient, user: User, stream_id: int
) -> ChatMessageCounterResponse:
    response = await satellites.send(client, "GET", f"/stats/chat/{stream_id}", user=user)
    return satellites.parse(response, CHAT_MESSAGES)


async def get_top_chat_messages(
    client: httpx.AsyncClient, user: User, limit: int
) -> list[ChatMessageCounterResponse]:
    response = await satellites.send(
        client, "GET", "/stats/chat/top", user=user, params={"limit": limit}
    )
    return satellites.parse(response, CHAT_MESSAGES_LIST)


async def get_player_event_counts(
    client: httpx.AsyncClient, user: User, stream_id: int
) -> PlayerEventCountersResponse:
    response = await satellites.send(client, "GET", f"/stats/player/{stream_id}", user=user)
    return satellites.parse(response, PLAYER_EVENTS)
