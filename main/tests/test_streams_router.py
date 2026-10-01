from datetime import timedelta

import pytest

from app.models import Stream
from app.models.stream import utcnow

PAYLOAD = {"title": "Speedrun any%", "game": "Celeste"}


def auth_headers(client, username="alice"):
    client.post("/auth/register", json={"username": username, "password": "s3cret-pass"})
    response = client.post(
        "/auth/login", data={"username": username, "password": "s3cret-pass"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_create_stream_returns_created_session(client):
    response = client.post("/streams", json=PAYLOAD, headers=auth_headers(client))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "id", "streamer", "title", "game", "status", "created_at", "started_at", "ended_at"
    }
    assert body["status"] == "created"
    assert body["title"] == "Speedrun any%"
    assert body["streamer"]["username"] == "alice"
    assert body["started_at"] is None
    assert body["ended_at"] is None


def test_create_stream_requires_auth(client):
    assert client.post("/streams", json=PAYLOAD).status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "game": "Celeste"},
        {"title": "x" * 101, "game": "Celeste"},
        {"title": "Speedrun", "game": ""},
        {"title": "Speedrun", "game": "x" * 51},
        {"title": "Speedrun"},
    ],
)
def test_create_stream_invalid_payload_returns_422(client, payload):
    response = client.post("/streams", json=payload, headers=auth_headers(client))
    assert response.status_code == 422


def test_create_stream_accepts_length_bounds(client):
    payload = {"title": "x" * 100, "game": "y" * 50}
    response = client.post("/streams", json=payload, headers=auth_headers(client))
    assert response.status_code == 201


def test_second_active_stream_returns_409(client):
    headers = auth_headers(client)
    client.post("/streams", json=PAYLOAD, headers=headers)

    response = client.post("/streams", json=PAYLOAD, headers=headers)

    assert response.status_code == 409


def test_other_streamer_can_create_a_stream(client):
    client.post("/streams", json=PAYLOAD, headers=auth_headers(client, "alice"))

    response = client.post("/streams", json=PAYLOAD, headers=auth_headers(client, "bob"))

    assert response.status_code == 201


def test_live_stream_blocks_a_new_one(client, db_session):
    headers = auth_headers(client)
    stream_id = client.post("/streams", json=PAYLOAD, headers=headers).json()["id"]
    db_session.get(Stream, stream_id).status = "live"
    db_session.commit()

    assert client.post("/streams", json=PAYLOAD, headers=headers).status_code == 409


def test_ended_stream_does_not_block_a_new_one(client, db_session):
    headers = auth_headers(client)
    stream_id = client.post("/streams", json=PAYLOAD, headers=headers).json()["id"]
    db_session.get(Stream, stream_id).status = "ended"
    db_session.commit()

    assert client.post("/streams", json=PAYLOAD, headers=headers).status_code == 201


def test_stale_created_stream_is_cancelled(client, db_session):
    headers = auth_headers(client)
    stream_id = client.post("/streams", json=PAYLOAD, headers=headers).json()["id"]
    db_session.get(Stream, stream_id).created_at = utcnow() - timedelta(minutes=11)
    db_session.commit()

    response = client.post("/streams", json=PAYLOAD, headers=headers)

    assert response.status_code == 201
    assert db_session.get(Stream, stream_id).status == "cancelled"


def test_recent_created_stream_is_not_cancelled(client, db_session):
    headers = auth_headers(client)
    stream_id = client.post("/streams", json=PAYLOAD, headers=headers).json()["id"]
    db_session.get(Stream, stream_id).created_at = utcnow() - timedelta(minutes=9)
    db_session.commit()

    assert client.post("/streams", json=PAYLOAD, headers=headers).status_code == 409
    assert db_session.get(Stream, stream_id).status == "created"


def test_get_stream_returns_detail(client):
    headers = auth_headers(client)
    stream_id = client.post("/streams", json=PAYLOAD, headers=headers).json()["id"]

    response = client.get(f"/streams/{stream_id}")

    assert response.status_code == 200
    assert response.json()["id"] == stream_id


def test_get_unknown_stream_returns_404(client):
    assert client.get("/streams/999").status_code == 404


def test_list_streams_filters_by_status(client, db_session):
    live_id = client.post(
        "/streams", json=PAYLOAD, headers=auth_headers(client, "alice")
    ).json()["id"]
    client.post("/streams", json=PAYLOAD, headers=auth_headers(client, "bob"))
    db_session.get(Stream, live_id).status = "live"
    db_session.commit()

    body = client.get("/streams", params={"status": "live"}).json()

    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [live_id]
    assert body["items"][0]["streamer"]["username"] == "alice"


def test_list_streams_is_paginated(client, db_session):
    for name in ("alice", "bob", "carol"):
        client.post("/streams", json=PAYLOAD, headers=auth_headers(client, name))

    body = client.get("/streams", params={"page": 2, "size": 2}).json()

    assert body["total"] == 3
    assert body["page"] == 2
    assert body["size"] == 2
    assert len(body["items"]) == 1


@pytest.mark.parametrize(
    "params", [{"status": "unknown"}, {"page": 0}, {"size": 0}, {"size": 101}]
)
def test_list_streams_invalid_query_returns_422(client, params):
    assert client.get("/streams", params=params).status_code == 422
