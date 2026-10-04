import logging
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from common.events import ItemType, SearchHit
from common.mqtt import MqttClient, NotConnectedError
from common.topics import SEARCH_HIT

logger = logging.getLogger(__name__)


def build_hits(
    item_type: ItemType,
    item_ids: Iterable[int | UUID],
    search_query: str,
    hit_at: datetime,
) -> list[SearchHit]:
    return [
        SearchHit(
            item_type=item_type,
            item_id=str(item_id),
            query=search_query,
            hit_at=hit_at,
        )
        for item_id in item_ids
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
