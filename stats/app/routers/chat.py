from typing import Annotated

from common.topics import CHAT_MESSAGE
from fastapi import APIRouter, Path, Query, Request, Response
from pydantic import TypeAdapter
from sqlalchemy import select

from app.cache import RedisDep, cache_key, read, write
from app.database import SessionDep
from app.models import Counter
from app.schemas import ChatMessageCountResponse
from app.utils import LIMIT_INTEGER

StreamId = Annotated[int, Path(gt=0, le=LIMIT_INTEGER)]
Limit = Annotated[int, Query(gt=0, le=500)]

ChatMessageList = TypeAdapter(list[ChatMessageCountResponse])

router = APIRouter(tags=["chat"])


# declared before /stats/chat/{stream_id}: otherwise "top" would be read as a
# stream_id, fail the int validation, and the route would always answer 422
@router.get("/stats/chat/top")
async def get_top_chat_messages(
    session: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
    limit: Limit = 10,
) -> list[ChatMessageCountResponse]:
    key = cache_key(request)
    cached = await read(redis, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return ChatMessageList.validate_json(cached)

    stmt = (
        select(Counter)
        .where(Counter.counter_type == CHAT_MESSAGE)
        .order_by(Counter.value.desc(), Counter.key)
        .limit(limit)
    )
    counters = await session.scalars(stmt)
    result = [
        ChatMessageCountResponse(stream_id=int(counter.key), count=counter.value)
        for counter in counters
    ]

    await write(redis, key, ChatMessageList.dump_json(result).decode())
    response.headers["X-Cache"] = "MISS"
    return result


@router.get("/stats/chat/{stream_id}")
async def get_chat_message_count(
    stream_id: StreamId,
    session: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
) -> ChatMessageCountResponse:
    key = cache_key(request)
    cached = await read(redis, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return ChatMessageCountResponse.model_validate_json(cached)

    stmt = select(Counter.value).where(
        Counter.key == str(stream_id),
        Counter.counter_type == CHAT_MESSAGE,
    )
    count = await session.scalar(stmt)
    result = ChatMessageCountResponse(stream_id=stream_id, count=count or 0)

    await write(redis, key, result.model_dump_json())
    response.headers["X-Cache"] = "MISS"
    return result