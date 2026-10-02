from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.dependencies import require_admin
from app.main import app as main_app
from app.models import User
from app.services.auth import create_access_token, make_admin, register

# require_admin is not used by any route yet: mount it on a test-only app
app = FastAPI()


@app.get("/admin-only")
def admin_only(user: Annotated[User, Depends(require_admin)]):
    return {"username": user.username}


@pytest.fixture
def admin_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_admin_is_allowed(admin_client, db_session):
    register(db_session, "alice", "s3cret-pass")
    admin = make_admin(db_session, "alice")

    response = admin_client.get("/admin-only", headers=auth_header(admin))

    assert response.status_code == 200
    assert response.json() == {"username": "alice"}


def test_user_gets_403(admin_client, db_session):
    user = register(db_session, "bob", "s3cret-pass")

    response = admin_client.get("/admin-only", headers=auth_header(user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin role required"}


def test_without_token_gets_401(admin_client):
    response = admin_client.get("/admin-only")

    assert response.status_code == 401


def test_me_returns_admin_role(db_session):
    register(db_session, "alice", "s3cret-pass")
    admin = make_admin(db_session, "alice")
    main_app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(main_app).get("/auth/me", headers=auth_header(admin))
    finally:
        main_app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
