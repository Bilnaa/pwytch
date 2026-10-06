from typing import Annotated, get_args

from common.events import PlayerEvent
from common.topics import PLAYER_EVENT
from fastapi import APIRouter, Path, Request, Response
from sqlalchemy import select

from app.cache import RedisDep, cache_key, read, write
from app.database import SessionDep
from app.models import Counter
from app.schemas import PlayerEventCountResponse
from app.utils import LIMIT_INTEGER

StreamId = Annotated[int, Path(gt=0, le=LIMIT_INTEGER)]

# the event types come from common, so they are written in only one place
EVENT_TYPES = get_args(PlayerEvent.model_fields["event_type"].annotation)

router = APIRouter(tags=["player"])


@router.get("/stats/player/{stream_id}")
async def get_player_event_counts(
    stream_id: StreamId,
    session: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
) -> PlayerEventCountResponse:
    key = cache_key(request)
    cached = await read(redis, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return PlayerEventCountResponse.model_validate_json(cached)

    keys = [f"{stream_id}:{event_type}" for event_type in EVENT_TYPES]
    stmt = select(Counter.key, Counter.value).where(
        Counter.counter_type == PLAYER_EVENT,
        Counter.key.in_(keys),
    )
    rows = (await session.execute(stmt)).all()

    # an event type that never happened has no row in the database: default to 0
    counts = dict.fromkeys(EVENT_TYPES, 0)
    for counter_key, value in rows:
        counts[counter_key.partition(":")[2]] = value
    result = PlayerEventCountResponse(stream_id=stream_id, **counts)

    await write(redis, key, result.model_dump_json())
    response.headers["X-Cache"] = "MISS"
    return result