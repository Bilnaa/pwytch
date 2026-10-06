from typing import Annotated

from common.events import TargetType
from common.topics import BOOKMARK_DELETED
from fastapi import APIRouter, Query, Request, Response
from pydantic import TypeAdapter
from sqlalchemy import select

from app.cache import RedisDep, cache_key, read, write
from app.database import SessionDep
from app.models import Counter
from app.schemas import BookmarkDeletedCountResponse

Limit = Annotated[int, Query(gt=0, le=500)]

BookmarkDeletedList = TypeAdapter(list[BookmarkDeletedCountResponse])

router = APIRouter(tags=["bookmarks"])


@router.get("/stats/bookmarks/deleted/top")
async def get_top_bookmark_deleted(
    session: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
    limit: Limit = 10,
    target_type: TargetType | None = None,
) -> list[BookmarkDeletedCountResponse]:
    key = cache_key(request)
    cached = await read(redis, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return BookmarkDeletedList.validate_json(cached)

    stmt = (
        select(Counter)
        .where(Counter.counter_type == BOOKMARK_DELETED)
        .order_by(Counter.value.desc(), Counter.key)
        .limit(limit)
    )
    if target_type:
        stmt = stmt.where(Counter.key.startswith(f"{target_type}:"))
    counters = await session.scalars(stmt)

    result = []
    for counter in counters:
        counter_target_type, _, counter_target_id = counter.key.partition(":")
        result.append(
            BookmarkDeletedCountResponse(
                target_type=counter_target_type,
                target_id=int(counter_target_id),
                count=counter.value,
            )
        )

    await write(redis, key, BookmarkDeletedList.dump_json(result).decode())
    response.headers["X-Cache"] = "MISS"
    return result


@router.get("/stats/bookmarks/deleted/{target_type}/{target_id}")
async def get_bookmark_deleted(
    target_type: TargetType,
    target_id: int,
    session: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
) -> BookmarkDeletedCountResponse:
    key = cache_key(request)
    cached = await read(redis, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return BookmarkDeletedCountResponse.model_validate_json(cached)

    stmt = select(Counter.value).where(
        Counter.key == f"{target_type}:{target_id}",
        Counter.counter_type == BOOKMARK_DELETED,
    )
    count = await session.scalar(stmt)
    result = BookmarkDeletedCountResponse(
        target_type=target_type, target_id=target_id, count=count or 0
    )

    await write(redis, key, result.model_dump_json())
    response.headers["X-Cache"] = "MISS"
    return result