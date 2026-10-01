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
