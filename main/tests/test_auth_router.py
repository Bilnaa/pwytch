import pytest


def test_register_returns_created_user(client):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "s3cret-pass"}
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "username", "display_name", "role"}
    assert body["username"] == "alice"
    assert body["display_name"] == "alice"
    assert body["role"] == "user"


def test_register_lowercases_username_and_keeps_display_name(client):
    response = client.post(
        "/auth/register", json={"username": "Alice_42", "password": "s3cret-pass"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice_42"
    assert body["display_name"] == "Alice_42"


def test_register_duplicate_username_returns_409(client):
    payload = {"username": "alice", "password": "s3cret-pass"}
    client.post("/auth/register", json=payload)

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409


def test_register_duplicate_username_with_other_case_returns_409(client):
    client.post("/auth/register", json={"username": "alice", "password": "s3cret-pass"})

    response = client.post(
        "/auth/register", json={"username": "Alice", "password": "s3cret-pass"}
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "al", "password": "s3cret-pass"},
        {"username": "a" * 31, "password": "s3cret-pass"},
        {"username": "alice-doe", "password": "s3cret-pass"},
        {"username": "alice doe", "password": "s3cret-pass"},
        {"username": "alice", "password": "short"},
        {"username": "alice"},
        {"password": "s3cret-pass"},
    ],
)
def test_register_invalid_payload_returns_422(client, payload):
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_register_accepts_username_bounds_and_underscore(client):
    for username in ("abc", "a" * 30, "alice_42"):
        response = client.post(
            "/auth/register", json={"username": username, "password": "s3cret-pass"}
        )
        assert response.status_code == 201


def login(client, username="alice", password="s3cret-pass"):
    return client.post(
        "/auth/login", data={"username": username, "password": password}
    )


def test_login_returns_bearer_token(client):
    client.post("/auth/register", json={"username": "alice", "password": "s3cret-pass"})

    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type"}
    assert body["token_type"] == "bearer"


def test_login_ignores_username_case(client):
    client.post("/auth/register", json={"username": "Alice", "password": "s3cret-pass"})

    response = login(client, username="ALICE")

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("username", "password"),
    [("alice", "wrong-pass"), ("bob", "s3cret-pass"), ("ali\x00ce", "s3cret-pass")],
)
def test_login_with_bad_credentials_returns_401(client, username, password):
    client.post("/auth/register", json={"username": "alice", "password": "s3cret-pass"})

    response = login(client, username, password)

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_login_with_json_body_returns_422(client):
    response = client.post(
        "/auth/login", json={"username": "alice", "password": "s3cret-pass"}
    )

    assert response.status_code == 422


def test_me_returns_current_user(client):
    client.post("/auth/register", json={"username": "Alice", "password": "s3cret-pass"})
    token = login(client).json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "username", "display_name", "role"}
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"


def test_me_without_token_returns_401(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
