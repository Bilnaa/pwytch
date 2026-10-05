from typing import Annotated

from common.events import TargetType
from common.topics import BOOKMARK_DELETED
from fastapi import APIRouter, Path, Query
from sqlalchemy import select

from app.database import SessionDep
from app.models import Counter
from app.schemas import BookmarkDeletedCountResponse
from app.utils import LIMIT_INTEGER

Limit = Annotated[int, Query(gt=0, le=500)]
TargetId = Annotated[int, Path(gt=0, le=LIMIT_INTEGER)]

router = APIRouter(tags=["bookmarks"])


@router.get("/stats/bookmarks/deleted/{target_type}/{target_id}")
async def get_bookmark_deleted(
    target_type: TargetType, target_id: TargetId, session: SessionDep
) -> BookmarkDeletedCountResponse:
    key = f"{target_type}:{target_id}"
    stmt = select(Counter.value).where(Counter.key == key, Counter.counter_type == BOOKMARK_DELETED)
    count = await session.scalar(stmt)
    response = BookmarkDeletedCountResponse(
        target_type=target_type, target_id=target_id, count=count or 0
    )
    return response


@router.get("/stats/bookmarks/deleted/top")
async def get_top_bookmark_deleted(
    session: SessionDep,
    limit: Limit = 10,
    target_type: TargetType | None = None,
) -> list[BookmarkDeletedCountResponse]:
    stmt = (
        select(Counter)
        .where(Counter.counter_type == BOOKMARK_DELETED)
        .order_by(Counter.value.desc(), Counter.key)
        .limit(limit)
    )

    if target_type:
        stmt = stmt.where(Counter.key.startswith(f"{target_type}:"))

    counters = await session.scalars(stmt)

    response = []
    for counter in counters:
        counter_target_type, _, counter_target_id = counter.key.partition(":")
        response.append(
            BookmarkDeletedCountResponse(
                target_type=counter_target_type,
                target_id=counter_target_id,
                count=counter.value,
            )
        )

    return response