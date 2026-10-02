from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Status(StrEnum):
    CREATED = "created"
    LIVE = "live"
    ENDED = "ended"
    CANCELLED = "cancelled"


class Stream(Base):
    __tablename__ = "streams"
    # at most one created/live session per streamer, enforced by the database
    __table_args__ = (
        Index(
            "uq_streams_one_active_per_streamer",
            "streamer_id",
            unique=True,
            sqlite_where=text("status IN ('created', 'live')"),
            postgresql_where=text("status IN ('created', 'live')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    streamer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    game: Mapped[str] = mapped_column(String(50))
    # created -> live -> ended, or created -> cancelled if the streamer never sent anything
    status: Mapped[str] = mapped_column(String(20), default=Status.CREATED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    streamer: Mapped[User] = relationship()
