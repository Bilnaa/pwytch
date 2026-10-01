from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    streamer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    game: Mapped[str] = mapped_column(String(50))
    # created -> live -> ended, or created -> cancelled if the streamer never sent anything
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    streamer: Mapped[User] = relationship()
