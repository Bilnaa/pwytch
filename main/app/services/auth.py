import re
from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import auth_settings
from app.models import User
from app.models.user import ADMIN_ROLE
from app.schemas.auth import USERNAME_PATTERN

password_hash = PasswordHash.recommended()

# Verified against when the username is unknown, so that a login takes the same
# time whether the account exists or not (avoids guessing usernames by timing)
DUMMY_HASH = password_hash.hash("dummypassword")


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserNotFoundError(Exception):
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


def authenticate(db: Session, username: str, password: str) -> User:
    if re.fullmatch(USERNAME_PATTERN, username) is None:
        user = None
    else:
        user = db.scalar(select(User).where(User.username == username.lower()))
    if user is None:
        verify_password(password, DUMMY_HASH)
        raise InvalidCredentialsError("Incorrect username or password")
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect username or password")
    return user


def create_access_token(user: User) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=auth_settings.access_token_expire_minutes
    )
    payload = {"sub": user.username, "exp": expire}
    return jwt.encode(
        payload, auth_settings.jwt_secret_key, algorithm=auth_settings.jwt_algorithm
    )


def get_user_from_token(db: Session, token: str) -> User:
    try:
        payload = jwt.decode(
            token,
            auth_settings.jwt_secret_key,
            algorithms=[auth_settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except InvalidTokenError as exc:
        raise InvalidCredentialsError("Could not validate credentials") from exc
    user = db.scalar(select(User).where(User.username == payload["sub"]))
    if user is None:
        raise InvalidCredentialsError("Could not validate credentials")
    return user


def get_user_by_username(db: Session, username: str) -> User:
    # usernames are stored in lowercase
    user = db.scalar(select(User).where(User.username == username.lower()))
    if user is None:
        raise UserNotFoundError(f"User {username!r} not found")
    return user


def make_admin(db: Session, username: str) -> User:
    user = get_user_by_username(db, username)
    user.role = ADMIN_ROLE
    db.commit()
    return user
