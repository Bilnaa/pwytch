import httpx
from common.events import ItemType
from pydantic import TypeAdapter

from app.models import User
from app.schemas.stats import CounterResponse
from app.services import satellites

COUNTER = TypeAdapter(CounterResponse)
COUNTER_LIST = TypeAdapter(list[CounterResponse])


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
