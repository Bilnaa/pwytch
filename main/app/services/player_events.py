import logging
import time
from collections import deque
from collections.abc import Callable
from threading import Lock

from common import topics
from common.events import PlayerEvent
from common.mqtt import MqttClient, NotConnectedError
from sqlalchemy.orm import Session

from app.models import User
from app.models.stream import utcnow
from app.services import streams as streams_service

logger = logging.getLogger(__name__)


class TooManyPlayerEventsError(Exception):
    pass


class PlayerEventLimiter:
    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self.clock = clock
        self.sent: dict[tuple[str, int], deque[float]] = {}
        self.lock = Lock()

    def check(self, client: str, stream_id: int) -> None:
        now = self.clock()
        with self.lock:
            self.forget_before(now - self.window_seconds)
            sent = self.sent.setdefault((client, stream_id), deque())
            if len(sent) >= self.max_events:
                raise TooManyPlayerEventsError("Too many player events, try again later")
            sent.append(now)

    def forget_before(self, limit: float) -> None:
        for key, sent in list(self.sent.items()):
            while sent and sent[0] <= limit:
                sent.popleft()
            if not sent:
                del self.sent[key]


limiter = PlayerEventLimiter(max_events=10, window_seconds=10)


def create_player_event(
    db: Session,
    client: str,
    stream_id: int,
    event_type: str,
    user: User | None,
) -> PlayerEvent:
    limiter.check(client, stream_id)
    streams_service.get_stream(db, stream_id)
    return PlayerEvent(
        stream_id=stream_id,
        event_type=event_type,
        user_id=user.id if user is not None else None,
        occurred_at=utcnow(),
    )


async def publish_player_event(mqtt: MqttClient, event: PlayerEvent) -> None:
    try:
        await mqtt.publish(topics.PLAYER_EVENT, event)
    except NotConnectedError as exc:
        logger.error("Player event %s of stream %s lost: %s", event.event_id, event.stream_id, exc)
