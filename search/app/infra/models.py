from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base


class Streamer(Base):
    __tablename__ = "streamers"
    __table_args__ = (
        Index(
            "ix_streamers_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    streamer_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    streamer_name: Mapped[str]
    search_text: Mapped[str]


class Stream(Base):
    __tablename__ = "streams"

    stream_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    streamer_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str | None]
    game: Mapped[str | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IndexedChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        # Sert le filtre par live et le tri du plus récent au plus ancien, sans Sort.
        Index(
            "ix_chat_messages_stream_id_sent_at_message_id",
            "stream_id",
            "sent_at",
            "message_id",
        ),
        # Même rôle pour la recherche tous lives confondus, sans filtre par live.
        Index("ix_chat_messages_sent_at_message_id", "sent_at", "message_id"),
    )

    # uuid4 généré par live-chat : type UUID natif sur Postgres, CHAR(32) sur SQLite.
    message_id: Mapped[UUID] = mapped_column(primary_key=True)
    stream_id: Mapped[int]
    author_id: Mapped[int]
    author_name: Mapped[str]
    content: Mapped[str]
    search_text: Mapped[str]
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


LATEST_STREAM_ORDER = (Stream.started_at.desc(), Stream.stream_id.desc())
