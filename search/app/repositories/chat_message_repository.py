from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.text import normalize
from app.models import IndexedChatMessage
from app.schemas import MessageResult

CHAT_SEARCH_LIMIT = 10


async def search_chat_messages(
    session: AsyncSession, stream_id: int | None, search_query: str
) -> list[MessageResult]:
    """Cherche dans le chat d'un live, ou de tous les lives si stream_id est None."""
    conditions = [
        IndexedChatMessage.search_text.contains(
            normalize(search_query), autoescape=True
        )
    ]
    if stream_id is not None:
        conditions.append(IndexedChatMessage.stream_id == stream_id)
    statement = (
        select(IndexedChatMessage)
        .where(*conditions)
        # Même ordre que les index (..., sent_at, message_id), lus à l'envers.
        .order_by(
            IndexedChatMessage.sent_at.desc(), IndexedChatMessage.message_id.desc()
        )
        .limit(CHAT_SEARCH_LIMIT)
    )
    rows = await session.scalars(statement)
    return [
        MessageResult.model_validate(message, from_attributes=True) for message in rows
    ]


async def get_chat_message(session: AsyncSession, message_id: UUID) -> IndexedChatMessage | None:
    return await session.get(IndexedChatMessage, message_id)


async def add_chat_message(session: AsyncSession, message: IndexedChatMessage) -> None:
    session.add(message)
