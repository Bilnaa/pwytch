from datetime import datetime

from sqlalchemy import DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base


class Streamer(Base):
    __tablename__ = "streamers"
    __table_args__ = (
        # Postgres-only options: SQLite creates a plain index and ignores them.
        Index(
            "ix_streamers_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    streamer_id: Mapped[str] = mapped_column(primary_key=True)
    streamer_name: Mapped[str]
    search_text: Mapped[str]


class Stream(Base):
    __tablename__ = "streams"

    stream_id: Mapped[str] = mapped_column(primary_key=True)
    streamer_id: Mapped[str] = mapped_column(index=True)
    # Nullable: a stream/ended event can arrive before its stream/started.
    title: Mapped[str | None]
    game: Mapped[str | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
