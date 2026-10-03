import logging
from datetime import datetime, timedelta

from common.events import StreamEnded, StreamStarted
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import Stream, User
from app.models.stream import Status, utcnow

logger = logging.getLogger(__name__)

# A session that nobody started streaming into after this long is abandoned
CREATED_TIMEOUT = timedelta(minutes=10)
ACTIVE_STATUSES = (Status.CREATED, Status.LIVE)


class ActiveStreamExistsError(Exception):
    pass


class StreamNotFoundError(Exception):
    pass


def cancel_stale_sessions(db: Session, streamer_id: int | None = None) -> None:
    query = select(Stream).where(
        Stream.status == Status.CREATED,
        Stream.created_at < utcnow() - CREATED_TIMEOUT,
    )
    if streamer_id is not None:
        query = query.where(Stream.streamer_id == streamer_id)
    for stream in db.scalars(query):
        stream.status = Status.CANCELLED
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
    try:
        db.commit()
    except IntegrityError as exc:
        # a concurrent request created an active session first
        db.rollback()
        raise ActiveStreamExistsError("You already have a stream in progress") from exc
    db.refresh(stream)
    return stream


def get_stream(db: Session, stream_id: int) -> Stream:
    stream = db.scalar(
        select(Stream).options(joinedload(Stream.streamer)).where(Stream.id == stream_id)
    )
    if stream is None:
        raise StreamNotFoundError("Stream not found")
    return stream


def list_streams(
    db: Session, status: str | None, page: int, size: int
) -> tuple[list[Stream], int]:
    cancel_stale_sessions(db)

    query = select(Stream)
    count = select(func.count(Stream.id))
    if status is not None:
        query = query.where(Stream.status == status)
        count = count.where(Stream.status == status)

    total = db.scalar(count)
    items = db.scalars(
        query.options(joinedload(Stream.streamer))
        .order_by(Stream.created_at.desc(), Stream.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(items), total


def mark_started(db: Session, stream_id: int, started_at: datetime) -> Stream:
    stream = get_stream(db, stream_id)
    if stream.status != Status.CREATED:
        # duplicated or late event, or the session was cancelled
        return stream
    stream.status = Status.LIVE
    stream.started_at = started_at
    db.commit()
    return stream


def record_started(db: Session, stream_id: int, started_at: datetime) -> Stream:
    stream = get_stream(db, stream_id)
    if stream.status == Status.CREATED:
        return mark_started(db, stream_id, started_at)
    if stream.status == Status.LIVE:
        stream.started_at = started_at
        db.commit()
    return stream


def mark_ended(db: Session, stream_id: int, ended_at: datetime) -> Stream:
    stream = get_stream(db, stream_id)
    if stream.status != Status.LIVE:
        return stream
    stream.status = Status.ENDED
    stream.ended_at = ended_at
    db.commit()
    return stream


def mark_over(db: Session, stream_id: int, at: datetime) -> Stream:
    stream = get_stream(db, stream_id)
    if stream.status == Status.LIVE:
        return mark_ended(db, stream_id, at)
    if stream.status == Status.CREATED:
        stream.status = Status.CANCELLED
        db.commit()
    return stream


def on_stream_started(db: Session, event: StreamStarted) -> None:
    try:
        stream = record_started(db, event.stream_id, event.started_at)
    except StreamNotFoundError:
        logger.warning("Ignored stream/started for the unknown stream %s", event.stream_id)
        return
    logger.info("Stream %s is %s", stream.id, stream.status)


def on_stream_ended(db: Session, event: StreamEnded) -> None:
    try:
        stream = mark_ended(db, event.stream_id, event.ended_at)
    except StreamNotFoundError:
        logger.warning("Ignored stream/ended for the unknown stream %s", event.stream_id)
        return
    logger.info("Stream %s is %s (%s)", stream.id, stream.status, event.reason)
