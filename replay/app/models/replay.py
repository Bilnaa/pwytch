from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Mp4Status(StrEnum):
    NONE = "none"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Replay(Base):
    __tablename__ = "replays"
    __table_args__ = (
        # Sert le tri de la liste (ended_at DESC, stream_id DESC), lu à l'envers.
        Index("ix_replays_ended_at_stream_id", "ended_at", "stream_id"),
    )

    # Un live donne un replay : l'id du live sert d'id public.
    stream_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    streamer_id: Mapped[int] = mapped_column(index=True)
    # Nuls tant que stream/started n'est pas arrivé (events dans le désordre).
    streamer_name: Mapped[str | None]
    title: Mapped[str | None]
    game: Mapped[str | None]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # NULL = live en cours : jamais exposé par les routes.
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float | None]
    # Stocke les valeurs ("none", ...) et non les noms de l'enum ; la contrainte CHECK refuse
    # toute autre chaîne, et server_default couvre une ligne insérée hors ORM.
    mp4_status: Mapped[Mp4Status] = mapped_column(
        Enum(
            Mp4Status,
            native_enum=False,
            create_constraint=True,
            name="mp4_status",
            length=16,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        default=Mp4Status.NONE,
        server_default=Mp4Status.NONE.value,
    )
