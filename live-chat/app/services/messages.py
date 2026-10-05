from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models.message import ChatMessage
from app.models.message_model import Author, MessageModel


async def save_message(message: MessageModel) -> None:
    # Stores the message in db
    # Schema may not exist if Postgres was down when the service started
    await init_db()
    # Fresh session per message: after a failure, the next message starts clean
    async with SessionLocal() as session:
        session.add(ChatMessage(
            id=message.id,
            stream_id=message.stream_id,
            author_id=message.author.id,
            author_username=message.author.username,
            content=message.content,
            sent_at=message.sent_at,
        ))
        await session.commit()


async def get_last_messages(stream_id: int, limit: int) -> list[MessageModel]:
    # Returns the last messages of the stream, oldest first based on the limit set
    await init_db()
    async with SessionLocal() as session:
        # Newest first to keep only the last ones (uses ix_chat_messages_stream_id_sent_at)
        rows = await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.stream_id == stream_id)
            .order_by(ChatMessage.sent_at.desc())
            .limit(limit)
        )
        return [
            MessageModel(
                id=row.id,
                stream_id=row.stream_id,
                author=Author(id=row.author_id, username=row.author_username),
                content=row.content,
                sent_at=row.sent_at,
            )
            for row in reversed(rows.all())
        ]
