from http import HTTPStatus

import pytest
from app.utils import LIMIT_INTEGER

OWNER_ID = 1
OTHER_USER_ID = 2


def create_header(user_id: int) -> dict[str, str]:
    return {
        "X-User-Id": str(user_id),
        "X-User-Name": "saul goodman",
        "X-User-Role": "lawyer",
    }


@pytest.fixture
def bookmark_payload():
    return {
        "target_type": "streamer",
        "target_id": 123,
        "label": "test",
        "note": "test note",
    }


@pytest.fixture
def bookmark_id(client, bookmark_payload) -> int:
    response = client.post(
        "/bookmarks",
        headers=create_header(OWNER_ID),
        json=bookmark_payload,
    )

    assert response.status_code == HTTPStatus.CREATED
    return response.json()["id"]


def test_create_bookmark_success(client, bookmark_payload):
    headers = create_header(OWNER_ID)

    response = client.post("/bookmarks", headers=headers, json=bookmark_payload)

    assert response.status_code == HTTPStatus.CREATED
    response_json = response.json()
    assert {key: response_json[key] for key in bookmark_payload} == bookmark_payload
    assert response_json["user_id"] == OWNER_ID
    assert response.headers["Location"] == f"/bookmarks/{response_json['id']}"


def test_create_bookmark_return_conflict(client, bookmark_payload, bookmark_id):
    # bookmark_id has already created the same bookmark for the owner
    response = client.post(
        "/bookmarks",
        headers=create_header(OWNER_ID),
        json=bookmark_payload,
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_create_same_target_for_another_user_success(
    client, bookmark_payload, bookmark_id
):
    response = client.post(
        "/bookmarks",
        headers=create_header(OTHER_USER_ID),
        json=bookmark_payload,
    )

    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.parametrize(
    "field, value",
    [
        ("label", " "),
        ("label", "a" * 101),
        ("note", "a" * 301),
        ("target_id", 0),
        ("target_id", -1),
        ("target_id", LIMIT_INTEGER + 1),
        ("target_type", "chaussette"),
    ],
)
def test_create_bookmark_return_unprocessable_entity(
    client, bookmark_payload, field, value
):
    bookmark_payload[field] = value

    response = client.post(
        "/bookmarks",
        headers=create_header(OWNER_ID),
        json=bookmark_payload,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_bookmark_return_unauthorized(client, bookmark_payload):
    response = client.post("/bookmarks", json=bookmark_payload)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_update_bookmark_success(client, bookmark_id):
    bookmark_update = {"label": "foo", "note": "bar"}

    response = client.patch(
        f"/bookmarks/{bookmark_id}",
        headers=create_header(OWNER_ID),
        json=bookmark_update,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["label"] == bookmark_update["label"]
    assert response.json()["note"] == bookmark_update["note"]


def test_update_only_note_keeps_label(client, bookmark_payload, bookmark_id):
    response = client.patch(
        f"/bookmarks/{bookmark_id}",
        headers=create_header(OWNER_ID),
        json={"note": "bar"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["note"] == "bar"
    assert response.json()["label"] == bookmark_payload["label"]


def test_update_note_to_null_clears_note(client, bookmark_id):
    response = client.patch(
        f"/bookmarks/{bookmark_id}",
        headers=create_header(OWNER_ID),
        json={"note": None},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["note"] is None


@pytest.mark.parametrize(
    "bookmark_update",
    [
        {"label": None},
        {"label": " "},
        {"target_id": 99},
    ],
)
def test_update_bookmark_unprocessable_entity(client, bookmark_id, bookmark_update):
    response = client.patch(
        f"/bookmarks/{bookmark_id}",
        headers=create_header(OWNER_ID),
        json=bookmark_update,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_bookmark_not_found(client):
    response = client.patch(
        "/bookmarks/999",
        headers=create_header(OWNER_ID),
        json={"label": "foo"},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_other_user_bookmark_not_found(client, bookmark_id):
    response = client.patch(
        f"/bookmarks/{bookmark_id}",
        headers=create_header(OTHER_USER_ID),
        json={"label": "hacked"},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_update_bookmark_unauthorized(client, bookmark_id):
    response = client.patch(f"/bookmarks/{bookmark_id}", json={"label": "foo"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_delete_bookmark_no_content(client, bookmark_id):
    response = client.delete(
        f"/bookmarks/{bookmark_id}", headers=create_header(OWNER_ID)
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b""


def test_delete_bookmark_not_found(client, bookmark_id):
    headers = create_header(OWNER_ID)
    first_response = client.delete(f"/bookmarks/{bookmark_id}", headers=headers)
    assert first_response.status_code == HTTPStatus.NO_CONTENT

    response = client.delete(f"/bookmarks/{bookmark_id}", headers=headers)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_other_user_bookmark_not_found(client, bookmark_id):
    response = client.delete(
        f"/bookmarks/{bookmark_id}", headers=create_header(OTHER_USER_ID)
    )

    assert response.status_code == HTTPStatus.NOT_FOUND

    # the bookmark must still exist: its owner can still delete it
    owner_response = client.delete(
        f"/bookmarks/{bookmark_id}", headers=create_header(OWNER_ID)
    )
    assert owner_response.status_code == HTTPStatus.NO_CONTENT


def test_delete_bookmark_unauthorized(client, bookmark_id):
    response = client.delete(f"/bookmarks/{bookmark_id}")

    assert response.status_code == HTTPStatus.UNAUTHORIZED