from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    # Last messages sent on stream X
    __table_args__ = (Index("ix_chat_messages_stream_id_sent_at", "stream_id", "sent_at"),)

    # id and sent_at come from MessageModel, so what is broadcast is exactly what is stored
    id: Mapped[UUID] = mapped_column(primary_key=True)
    stream_id: Mapped[int]
    # No foreign key to main's users so the username is kept as it was when the message was sent
    author_id: Mapped[int]
    author_username: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(String(500))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
