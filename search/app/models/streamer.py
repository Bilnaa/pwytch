from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


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
