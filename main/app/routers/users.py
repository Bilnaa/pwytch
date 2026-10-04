from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.auth import PublicUser
from app.services import auth as auth_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{username}", response_model=PublicUser)
def get_user(username: str, db: Annotated[Session, Depends(get_db)]):
    try:
        return auth_service.get_user_by_username(db, username)
    except auth_service.UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
