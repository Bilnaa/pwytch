from typing import Annotated

from common.topics import PLAYER_EVENT
from fastapi import APIRouter, Path
from sqlalchemy import select

from app.database import SessionDep
from app.models import Counter
from app.schemas import PlayerEventCountResponse
from app.utils import LIMIT_INTEGER

StreamId = Annotated[int, Path(gt=0, le=LIMIT_INTEGER)]

EVENT_TYPES = ["play", "pause", "stop"]

router = APIRouter(tags=["player"])


@router.get("/stats/player/{stream_id}")
async def get_player_event_counts(
    stream_id: StreamId, session: SessionDep
) -> PlayerEventCountResponse:
    keys = [f"{stream_id}:{event_type}" for event_type in EVENT_TYPES]
    stmt = select(Counter.key, Counter.value).where(
        Counter.counter_type == PLAYER_EVENT,
        Counter.key.in_(keys),
    )
    rows = (await session.execute(stmt)).all()

    # an event type that never happened has no row in the database: default to 0
    counts = dict.fromkeys(EVENT_TYPES, 0)
    for key, value in rows:
        event_type = key.partition(":")[2]
        counts[event_type] = value

    return PlayerEventCountResponse(stream_id=stream_id, **counts)