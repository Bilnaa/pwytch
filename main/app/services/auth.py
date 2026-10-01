from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User

password_hash = PasswordHash.recommended()


class UserAlreadyExistsError(Exception):
    pass


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def register(db: Session, username: str, password: str) -> User:
    display_name = username
    username = username.lower()

    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise UserAlreadyExistsError("Username already registered")

    user = User(
        username=username,
        display_name=display_name,
        hashed_password=hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError("Username already registered") from exc
    db.refresh(user)
    return user
