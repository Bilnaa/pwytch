from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.auth import PublicUser
from app.services import auth as auth_service

router = APIRouter(prefix="/users", tags=["users"])

MAX_POSTGRES_INTEGER = 2_147_483_647
UserId = Annotated[int, Field(ge=1, le=MAX_POSTGRES_INTEGER)]


# A bookmark of a streamer only has its id: the front gets the names of a whole
# page of bookmarks in one call (?id=1&id=7) to link them to the channels
@router.get("", response_model=list[PublicUser], summary="Get several users by id")
def list_users(
    db: Annotated[Session, Depends(get_db)],
    user_ids: Annotated[list[UserId], Query(alias="id", min_length=1, max_length=100)],
):
    return auth_service.get_users_by_ids(db, user_ids)


@router.get("/{username}", response_model=PublicUser)
def get_user(username: str, db: Annotated[Session, Depends(get_db)]):
    try:
        return auth_service.get_user_by_username(db, username)
    except auth_service.UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
