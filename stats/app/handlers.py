from common.events import BookmarkDeleted, SearchHit
from common.topics import BOOKMARK_DELETED, SEARCH_HIT

from app.counters import increment_counter
from app.database import SessionLocal


async def on_search_hit(search_hit: SearchHit) -> None:
    key = f"{search_hit.item_type}:{search_hit.item_id}"
    async with SessionLocal() as session:
        await increment_counter(session, SEARCH_HIT, key)


async def on_bookmark_deleted(bookmark_deleted: BookmarkDeleted) -> None:
    key = f"{bookmark_deleted.target_type}:{bookmark_deleted.target_id}"
    async with SessionLocal() as session:
        await increment_counter(session, BOOKMARK_DELETED, key)