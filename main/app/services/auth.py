import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User

SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}


class UserAlreadyExistsError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT_PARAMS)
    return f"{salt.hex()}${digest.hex()}"


def register(db: Session, username: str, password: str) -> User:
    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise UserAlreadyExistsError("Username already registered")

    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError("Username already registered") from exc
    db.refresh(user)
    return user
