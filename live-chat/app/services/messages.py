from app.db import SessionLocal, init_db
from app.models.message import ChatMessage
from app.models.message_model import MessageModel


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
