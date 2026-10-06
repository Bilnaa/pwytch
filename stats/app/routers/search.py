from typing import Annotated

from common.events import ItemType
from common.topics import SEARCH_HIT
from fastapi import APIRouter, Query, Request, Response
from pydantic import TypeAdapter
from sqlalchemy import select

from app.cache import RedisDep, cache_key, read, write
from app.database import SessionDep
from app.models import Counter
from app.schemas import SearchCountResponse
from app.utils import get_item_id, get_item_type

Limit = Annotated[int, Query(gt=0, le=500)]

# a list has no model_dump_json: the adapter does it for list[SearchCountResponse]
CounterList = TypeAdapter(list[SearchCountResponse])

router = APIRouter(tags=["search"])


@router.get("/stats/search/top")
async def get_top_searched(
    session: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
    limit: Limit = 10,
    item_type: ItemType | None = None,
) -> list[SearchCountResponse]:
    key = cache_key(request)
    cached = await read(redis, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return CounterList.validate_json(cached)

    stmt = (
        select(Counter)
        .where(Counter.counter_type == SEARCH_HIT)
        .order_by(Counter.value.desc(), Counter.key)
        .limit(limit)
    )
    if item_type:
        stmt = stmt.where(Counter.key.startswith(f"{item_type}:"))
    counters = await session.scalars(stmt)
    result = [
        SearchCountResponse(
            item_id=get_item_id(counter.key),
            item_type=get_item_type(counter.key),
            count=counter.value,
        )
        for counter in counters
    ]

    await write(redis, key, CounterList.dump_json(result).decode())
    response.headers["X-Cache"] = "MISS"
    return result


@router.get("/stats/search/{item_type}/{item_id}")
async def get_search_count(
    item_type: ItemType,
    item_id: str,
    session: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
) -> SearchCountResponse:
    key = cache_key(request)
    cached = await read(redis, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return SearchCountResponse.model_validate_json(cached)

    stmt = select(Counter.value).where(
        Counter.key == f"{item_type}:{item_id}",
        Counter.counter_type == SEARCH_HIT,
    )
    count = await session.scalar(stmt)
    result = SearchCountResponse(item_type=item_type, item_id=item_id, count=count or 0)

    await write(redis, key, result.model_dump_json())
    response.headers["X-Cache"] = "MISS"
    return result