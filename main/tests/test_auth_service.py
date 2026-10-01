from datetime import datetime

import pytest
from sqlalchemy import update

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.models import User
from app.services.auth import (
    UserAlreadyExistsError,
    hash_password,
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
