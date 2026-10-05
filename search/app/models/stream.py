from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Stream(Base):
    __tablename__ = "streams"

    stream_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    streamer_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str | None]
    game: Mapped[str | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

