from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import update

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import auth_settings
from app.models import User
from app.services.auth import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
    authenticate,
    create_access_token,
    get_user_from_token,
    hash_password,
    make_admin,
    register,
    verify_password,
)


def test_hash_password_is_salted():
    first = hash_password("s3cret-pass")
    second = hash_password("s3cret-pass")

    assert first != second
    assert "s3cret-pass" not in first


def test_verify_password():
    hashed = hash_password("s3cret-pass")

    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_verify_password_with_hash_made_with_other_params():
    old_hash = PasswordHash((Argon2Hasher(time_cost=2, memory_cost=19456),))
    hashed = old_hash.hash("s3cret-pass")

    assert verify_password("s3cret-pass", hashed)


def test_register_persists_user(db_session):
    user = register(db_session, "alice", "s3cret-pass")

    assert user.id is not None
    stored = db_session.get(User, user.id)
    assert stored.username == "alice"
    assert stored.role == "user"
    assert stored.hashed_password != "s3cret-pass"
    assert stored.created_at is not None
    assert stored.updated_at is not None


def test_register_rejects_duplicate_username(db_session):
    register(db_session, "alice", "s3cret-pass")

    with pytest.raises(UserAlreadyExistsError):
        register(db_session, "alice", "other-pass-123")


def test_register_stores_lowercase_username_and_display_name(db_session):
    user = register(db_session, "Alice", "s3cret-pass")

    stored = db_session.get(User, user.id)
    assert stored.username == "alice"
    assert stored.display_name == "Alice"


def test_register_rejects_duplicate_username_ignoring_case(db_session):
    register(db_session, "alice", "s3cret-pass")

    with pytest.raises(UserAlreadyExistsError):
        register(db_session, "ALICE", "other-pass-123")


def test_updated_at_is_refreshed_on_update(db_session):
    user = register(db_session, "alice", "s3cret-pass")
    old = datetime(2000, 1, 1)
    db_session.execute(update(User).where(User.id == user.id).values(updated_at=old))
    db_session.commit()

    user.username = "alice2"
    db_session.commit()
    db_session.refresh(user)

    assert user.updated_at.year != 2000


def test_authenticate_returns_user(db_session):
    created = register(db_session, "alice", "s3cret-pass")

    user = authenticate(db_session, "alice", "s3cret-pass")

    assert user.id == created.id


def test_authenticate_ignores_username_case(db_session):
    created = register(db_session, "Alice", "s3cret-pass")

    user = authenticate(db_session, "ALICE", "s3cret-pass")

    assert user.id == created.id


def test_authenticate_rejects_wrong_password(db_session):
    register(db_session, "alice", "s3cret-pass")

    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, "alice", "wrong-pass")


@pytest.mark.parametrize("username", ["ali\x00ce", "alice-doe", "al", "a" * 31])
def test_authenticate_rejects_invalid_username_without_querying_db(
    db_session, username
):
    db_session.close()
    db_session.bind = None  # any query would now fail

    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, username, "s3cret-pass")


def test_authenticate_rejects_unknown_username(db_session):
    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, "bob", "s3cret-pass")


def test_create_access_token_contains_username_and_expiry(db_session):
    user = register(db_session, "alice", "s3cret-pass")

    payload = jwt.decode(
        create_access_token(user),
        auth_settings.jwt_secret_key,
        algorithms=[auth_settings.jwt_algorithm],
    )

    assert payload["sub"] == "alice"
    expire = datetime.fromtimestamp(payload["exp"], timezone.utc)
    expected = datetime.now(timezone.utc) + timedelta(
        minutes=auth_settings.access_token_expire_minutes
    )
    assert abs(expire - expected) < timedelta(seconds=10)


def test_get_user_from_token(db_session):
    user = register(db_session, "alice", "s3cret-pass")

    assert get_user_from_token(db_session, create_access_token(user)).id == user.id


def test_get_user_from_token_rejects_expired_token(db_session):
    register(db_session, "alice", "s3cret-pass")
    token = jwt.encode(
        {"sub": "alice", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        auth_settings.jwt_secret_key,
        algorithm=auth_settings.jwt_algorithm,
    )

    with pytest.raises(InvalidCredentialsError):
        get_user_from_token(db_session, token)


def test_get_user_from_token_rejects_token_without_exp(db_session):
    register(db_session, "alice", "s3cret-pass")
    token = jwt.encode(
        {"sub": "alice"},
        auth_settings.jwt_secret_key,
        algorithm=auth_settings.jwt_algorithm,
    )

    with pytest.raises(InvalidCredentialsError):
        get_user_from_token(db_session, token)


def test_get_user_from_token_rejects_other_secret(db_session):
    register(db_session, "alice", "s3cret-pass")
    token = jwt.encode(
        {"sub": "alice", "exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
        "another-secret-key-at-least-32-bytes",
        algorithm="HS256",
    )

    with pytest.raises(InvalidCredentialsError):
        get_user_from_token(db_session, token)


def test_get_user_from_token_rejects_token_without_sub(db_session):
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
        auth_settings.jwt_secret_key,
        algorithm=auth_settings.jwt_algorithm,
    )

    with pytest.raises(InvalidCredentialsError):
        get_user_from_token(db_session, token)


def test_get_user_from_token_rejects_deleted_user(db_session):
    user = register(db_session, "alice", "s3cret-pass")
    token = create_access_token(user)
    db_session.delete(user)
    db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        get_user_from_token(db_session, token)


def test_make_admin_gives_admin_role(db_session):
    register(db_session, "alice", "s3cret-pass")

    user = make_admin(db_session, "Alice")

    assert user.role == "admin"
    assert db_session.get(User, user.id).role == "admin"


def test_make_admin_unknown_user_raises(db_session):
    with pytest.raises(UserNotFoundError):
        make_admin(db_session, "ghost")
