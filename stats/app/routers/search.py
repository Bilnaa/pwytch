from typing import Annotated

from common.events import ItemType
from common.topics import SEARCH_HIT
from fastapi import APIRouter, Query
from sqlalchemy import select

from app.database import SessionDep
from app.models import Counter
from app.schemas import CounterResponse
from app.utils import get_item_id, get_item_type

Limit = Annotated[int, Query(gt=0, le=500)]


router = APIRouter(tags=["search"])


@router.get("/stats/search/{item_type}/{item_id}")
async def get_searched(item_type: ItemType, item_id: str, session: SessionDep) -> CounterResponse:
    key = f"{item_type}:{item_id}"
    stmt = select(Counter.value).where(Counter.key == key, Counter.counter_type == SEARCH_HIT)
    count = await session.scalar(stmt)
    response = CounterResponse(item_type=item_type, item_id=item_id, count=count or 0)
    return response


@router.get("/stats/search/top")
async def get_top_searched(
    session: SessionDep,
    limit: Limit = 10,
    item_type: ItemType | None = None,
) -> list[CounterResponse]:
    stmt = (
        select(Counter)
        .where(Counter.counter_type == SEARCH_HIT)
        .order_by(
            Counter.value.desc(),
            Counter.key,
        )
        .limit(limit)
    )

    if item_type:
        stmt = stmt.where(Counter.key.startswith(f"{item_type}:"))

    counters = await session.scalars(stmt)

    response = [
        CounterResponse(
            item_id=get_item_id(counter.key),
            item_type=get_item_type(counter.key),
            count=counter.value,
        )
        for counter in counters
    ]

    return response
