from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Stream, User
from app.models.stream import utcnow

# A session that nobody started streaming into after this long is abandoned
CREATED_TIMEOUT = timedelta(minutes=10)
ACTIVE_STATUSES = ("created", "live")


class ActiveStreamExistsError(Exception):
    pass


class StreamNotFoundError(Exception):
    pass


def cancel_stale_sessions(db: Session, streamer_id: int) -> None:
    stale = db.scalars(
        select(Stream).where(
            Stream.streamer_id == streamer_id,
            Stream.status == "created",
            Stream.created_at < utcnow() - CREATED_TIMEOUT,
        )
    )
    for stream in stale:
        stream.status = "cancelled"
    db.commit()


def create_stream(db: Session, streamer: User, title: str, game: str) -> Stream:
    cancel_stale_sessions(db, streamer.id)

    active = db.scalar(
        select(Stream.id).where(
            Stream.streamer_id == streamer.id, Stream.status.in_(ACTIVE_STATUSES)
        )
    )
    if active is not None:
        raise ActiveStreamExistsError("You already have a stream in progress")

    stream = Stream(streamer_id=streamer.id, title=title, game=game)
    db.add(stream)
    db.commit()
    db.refresh(stream)
    return stream


def get_stream(db: Session, stream_id: int) -> Stream:
    stream = db.get(Stream, stream_id)
    if stream is None:
        raise StreamNotFoundError("Stream not found")
    return stream


def list_streams(
    db: Session, status: str | None, page: int, size: int
) -> tuple[list[Stream], int]:
    query = select(Stream)
    if status is not None:
        query = query.where(Stream.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.options(joinedload(Stream.streamer))
        .order_by(Stream.created_at.desc(), Stream.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(items), total


def mark_started(db: Session, stream_id: int, started_at: datetime) -> Stream:
    stream = get_stream(db, stream_id)
    stream.status = "live"
    stream.started_at = started_at
    db.commit()
    return stream


def mark_ended(db: Session, stream_id: int, ended_at: datetime) -> Stream:
    stream = get_stream(db, stream_id)
    stream.status = "ended"
    stream.ended_at = ended_at
    db.commit()
    return stream
