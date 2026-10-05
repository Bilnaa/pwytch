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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.database import SessionDep
from app.dependencies import get_mqtt
from app.events import publish_bookmark_deleted
from app.models import Bookmark
from app.schemas import BookmarkCreate, BookmarkResponse, BookmarkUpdate, TargetType
from app.utils import LIMIT_INTEGER

router = APIRouter(tags=["bookmarks"])


BookmarkId = Annotated[int, Path(gt=0, le=LIMIT_INTEGER)]
PageNumber = Annotated[int, Query(ge=1, le=LIMIT_INTEGER)]
TargetId = Annotated[int, Query(gt=0, le=LIMIT_INTEGER)]
PageSize = Annotated[int, Query(ge=1, le=100)]
MqttDep = Annotated[MqttClient, Depends(get_mqtt)]

@router.patch("/bookmarks/{bookmark_id}", response_model=BookmarkResponse)
def update_bookmarks(
    bookmark_id: BookmarkId,
    request: BookmarkUpdate,
    user: CurrentUser,
    session: SessionDep
) -> BookmarkResponse:
    stmt = select(Bookmark).where(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id
    )
    bookmark = session.scalar(stmt)

    if bookmark is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='bookmark not found')

    update_bookmark_dict = request.model_dump(exclude_unset=True)

    for key, value in update_bookmark_dict.items():
        setattr(bookmark, key, value)

    session.commit()
    return bookmark


@router.post("/bookmarks", status_code=HTTPStatus.CREATED, response_model=BookmarkResponse)
def create_bookmarks(
    request: BookmarkCreate, 
    user: CurrentUser,
    session: SessionDep,
    response: Response
) -> BookmarkResponse:
    bookmark = Bookmark(
        user_id=user.id,
        target_type=request.target_type,
        target_id=request.target_id,
        label=request.label,
        note=request.note
    )
    session.add(bookmark)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail='bookmark already exists')

    response.headers["Location"] = f"/bookmarks/{bookmark.id}"
    return bookmark


@router.delete("/bookmarks/{bookmark_id}", status_code=HTTPStatus.NO_CONTENT)
def delete_bookmarks(
    bookmark_id: BookmarkId, 
    user: CurrentUser, 
    session: SessionDep, 
    background_tasks: BackgroundTasks,
    mqtt: MqttDep
) -> None:
    stmt = select(Bookmark).where(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id
    )
    bookmark = session.scalar(stmt)

    if bookmark is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='bookmark not found')

    event = BookmarkDeleted(
        bookmark_id=bookmark_id,
        target_type=bookmark.target_type,
        target_id=bookmark.target_id,
        user_id=bookmark.user_id,
        deleted_at=datetime.now(UTC),
    )
    session.delete(bookmark)
    session.commit()
    background_tasks.add_task(publish_bookmark_deleted, mqtt, event)


@router.get("/bookmarks", response_model=Page[BookmarkResponse])
def get_bookmarks(
    user: CurrentUser,
    session: SessionDep,
    target_type: TargetType | None = None,
    target_id: TargetId | None = None,
    page: PageNumber = 1,
    size: PageSize = 20,
) -> Page[BookmarkResponse]:
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

    return Page(
        items=[
            BookmarkResponse.model_validate(bookmark, from_attributes=True)
            for bookmark in bookmarks
        ],
        total=total or 0,
        page=page,
        size=size,
    )


@router.get("/bookmarks/{bookmark_id}", response_model=BookmarkResponse)
def get_bookmark(
    bookmark_id: BookmarkId, user: CurrentUser, session: SessionDep
) -> Bookmark:
    stmt = select(Bookmark).where(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id,
    )
    bookmark = session.scalar(stmt)

    if bookmark is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="bookmark not found")

    return bookmark