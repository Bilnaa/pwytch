from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated

from common.events import BookmarkDeleted
from common.identity import CurrentUser
from common.mqtt import MqttClient
from common.pagination import Page
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
)
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.cache import (
    bookmark_key,
    bump_version,
    get_redis,
    get_version,
    list_key,
    read,
    write,
)
from app.database import SessionDep
from app.dependencies import get_mqtt
from app.events import publish_bookmark_deleted
from app.models import Bookmark
from app.schemas import BookmarkCreate, BookmarkResponse, BookmarkUpdate, TargetType
from app.utils import LIMIT_INTEGER

router = APIRouter(tags=["bookmarks"])

BookmarkId = Annotated[int, Path(gt=0, le=LIMIT_INTEGER)]
PageNumber = Annotated[int, Query(ge=1, le=LIMIT_INTEGER)]
PageSize = Annotated[int, Query(ge=1, le=100)]
TargetId = Annotated[int, Query(gt=0, le=LIMIT_INTEGER)]
MqttDep = Annotated[MqttClient, Depends(get_mqtt)]
RedisDep = Annotated[Redis, Depends(get_redis)]


@router.patch("/bookmarks/{bookmark_id}", response_model=BookmarkResponse)
def update_bookmarks(
    bookmark_id: BookmarkId,
    request: BookmarkUpdate,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
) -> Bookmark:
    stmt = select(Bookmark).where(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id,
    )
    bookmark = session.scalar(stmt)
    if bookmark is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="bookmark not found")

    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(bookmark, key, value)

    session.commit()
    bump_version(redis, user.id)
    return bookmark


@router.post("/bookmarks", status_code=HTTPStatus.CREATED, response_model=BookmarkResponse)
def create_bookmarks(
    request: BookmarkCreate,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    response: Response,
) -> Bookmark:
    bookmark = Bookmark(
        user_id=user.id,
        target_type=request.target_type,
        target_id=request.target_id,
        label=request.label,
        note=request.note,
    )
    session.add(bookmark)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="bookmark already exists")

    bump_version(redis, user.id)
    response.headers["Location"] = f"/bookmarks/{bookmark.id}"
    return bookmark


@router.delete("/bookmarks/{bookmark_id}", status_code=HTTPStatus.NO_CONTENT)
def delete_bookmarks(
    bookmark_id: BookmarkId,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    mqtt: MqttDep,
    background_tasks: BackgroundTasks,
) -> None:
    stmt = select(Bookmark).where(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id,
    )
    bookmark = session.scalar(stmt)
    if bookmark is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="bookmark not found")

    event = BookmarkDeleted(
        bookmark_id=bookmark_id,
        target_type=bookmark.target_type,
        target_id=bookmark.target_id,
        user_id=bookmark.user_id,
        deleted_at=datetime.now(UTC),
    )
    session.delete(bookmark)
    session.commit()
    bump_version(redis, user.id)
    background_tasks.add_task(publish_bookmark_deleted, mqtt, event)


@router.get("/bookmarks", response_model=Page[BookmarkResponse])
def get_bookmarks(
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    response: Response,
    target_type: TargetType | None = None,
    target_id: TargetId | None = None,
    page: PageNumber = 1,
    size: PageSize = 20,
) -> Page[BookmarkResponse]:
    # read the version BEFORE the database: a write that happens meanwhile bumps it,
    # so what we cache below can never be read again
    version = get_version(redis, user.id)
    key = None
    if version is not None:
        key = list_key(user.id, version, target_type, target_id, page, size)
        cached = read(redis, key)
        if cached is not None:
            response.headers["X-Cache"] = "HIT"
            return Page[BookmarkResponse].model_validate_json(cached)

    conditions = [Bookmark.user_id == user.id]
    if target_type is not None:
        conditions.append(Bookmark.target_type == target_type)
    if target_id is not None:
        conditions.append(Bookmark.target_id == target_id)

    total = session.scalar(
        select(func.count()).select_from(Bookmark).where(*conditions)
    )
    stmt = (
        select(Bookmark)
        .where(*conditions)
        .order_by(Bookmark.created_at.desc(), Bookmark.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    bookmarks = session.scalars(stmt).all()

    result = Page[BookmarkResponse](
        items=[
            BookmarkResponse.model_validate(bookmark, from_attributes=True)
            for bookmark in bookmarks
        ],
        total=total or 0,
        page=page,
        size=size,
    )
    if key is not None:
        write(redis, key, result.model_dump_json())
    response.headers["X-Cache"] = "MISS"
    return result


@router.get("/bookmarks/{bookmark_id}", response_model=BookmarkResponse)
def get_bookmark(
    bookmark_id: BookmarkId,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    response: Response,
) -> BookmarkResponse:
    version = get_version(redis, user.id)
    key = None
    if version is not None:
        key = bookmark_key(user.id, version, bookmark_id)
        cached = read(redis, key)
        if cached is not None:
            response.headers["X-Cache"] = "HIT"
            return BookmarkResponse.model_validate_json(cached)

    stmt = select(Bookmark).where(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id,
    )
    bookmark = session.scalar(stmt)
    if bookmark is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="bookmark not found")

    result = BookmarkResponse.model_validate(bookmark, from_attributes=True)
    if key is not None:
        write(redis, key, result.model_dump_json())
    response.headers["X-Cache"] = "MISS"
    return result