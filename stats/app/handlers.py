from common.events import SearchHit
from common.topics import SEARCH_HIT

from app.counters import increment_counter
from app.database import SessionLocal


async def on_search_hit(search_hit: SearchHit) -> None:
    key = f"{search_hit.item_type}:{search_hit.item_id}"
    async with SessionLocal() as session:
        await increment_counter(session, SEARCH_HIT, key)
