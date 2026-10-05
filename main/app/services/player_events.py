import logging

from common import topics
from common.events import PlayerEvent
from common.mqtt import MqttClient, NotConnectedError
from sqlalchemy.orm import Session

from app.models import User
from app.models.stream import utcnow
from app.services import streams as streams_service

logger = logging.getLogger(__name__)


def create_player_event(
    db: Session, stream_id: int, event_type: str, user: User | None
) -> PlayerEvent:
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
