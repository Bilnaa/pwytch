import logging
from datetime import datetime

from common.events import ItemType, SearchHit
from common.mqtt import MqttClient, NotConnectedError
from common.topics import SEARCH_HIT

from app.schemas import MessageResult, StreamerResult

logger = logging.getLogger(__name__)


def streamer_hits(
    results: list[StreamerResult], search_query: str, hit_at: datetime
) -> list[SearchHit]:
    return [
        SearchHit(
            item_type=ItemType.STREAMER,
            item_id=str(result.streamer_id),
            query=search_query,
            hit_at=hit_at,
        )
        for result in results
    ]


def message_hits(
    results: list[MessageResult], search_query: str, hit_at: datetime
) -> list[SearchHit]:
    return [
        SearchHit(
            item_type=ItemType.MESSAGE,
            item_id=str(result.message_id),
            query=search_query,
            hit_at=hit_at,
        )
        for result in results
    ]


async def publish_hits(mqtt: MqttClient, hits: list[SearchHit]) -> None:
    """Publie un event par hit, appelé en tâche de fond après la réponse.

    Ne lève jamais : une exception dans une tâche de fond finirait en
    « Exception in ASGI application » au lieu d'une erreur journalisée.
    """
    for index, hit in enumerate(hits):
        try:
            await mqtt.publish(SEARCH_HIT, hit)
        except NotConnectedError as exc:
            # Broker coupé ou figé : les suivants échoueraient aussi, une seule ligne suffit.
            logger.error(
                "%d search/hit events not published: %s", len(hits) - index, exc
            )
            return
        except Exception:
            # Cas inattendu : la trace sert à corriger, la recherche a déjà répondu.
            logger.exception("%d search/hit events not published", len(hits) - index)
            return
