from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from http import HTTPStatus

from common.identity import CurrentUser
from app.schemas import BookmarkCreate, BookmarkResponse, BookmarkUpdate
from app.database import SessionDep
from app.models import Bookmark
from app.utils import LIMIT_INTEGER

router = APIRouter(tags=["bookmarks"])


BookmarkId = Annotated[int, Path(gt=0, le=LIMIT_INTEGER)]


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
def delete_bookmarks(bookmark_id: BookmarkId, user: CurrentUser, session: SessionDep) -> None:
    stmt = select(Bookmark).where(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id
    )
    bookmark = session.scalar(stmt)

    if bookmark is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='bookmark not found')

    session.delete(bookmark)
    session.commit()
    return