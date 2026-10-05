from common.events import ItemType
from common.pagination import Page
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import chat_message_repository, streamer_repository
from app.schemas import MessageResult, StreamerResult
from app.services.hit_service import HitPublisher


async def search_streamers(
    session: AsyncSession, hits: HitPublisher, search_query: str, page: int, size: int
) -> Page[StreamerResult]:
    results, total = await streamer_repository.search_streamers(session, search_query, page, size)
    hits.schedule(ItemType.STREAMER, [result.streamer_id for result in results], search_query)
    return Page[StreamerResult](items=results, total=total, page=page, size=size)


async def search_chat_messages(
    session: AsyncSession, hits: HitPublisher, stream_id: int, search_query: str
) -> list[MessageResult]:
    results = await chat_message_repository.search_chat_messages(session, stream_id, search_query)
    hits.schedule(ItemType.MESSAGE, [result.message_id for result in results], search_query)
    return results


async def search_all_chat_messages(
    session: AsyncSession, hits: HitPublisher, search_query: str
) -> list[MessageResult]:
    results = await chat_message_repository.search_chat_messages(
        session, stream_id=None, search_query=search_query
    )
    hits.schedule(ItemType.MESSAGE, [result.message_id for result in results], search_query)
    return results
