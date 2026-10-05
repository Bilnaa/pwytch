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


def create_bookmark(client, bookmark_payload, **overrides) -> int:
    response = client.post(
        "/bookmarks",
        headers=create_header(OWNER_ID),
        json={**bookmark_payload, **overrides},
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()["id"]


def list_bookmarks(client, **params):
    response = client.get("/bookmarks", headers=create_header(OWNER_ID), params=params)
    assert response.status_code == HTTPStatus.OK
    return response.json()


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


def test_list_bookmarks_empty(client):
    response = client.get("/bookmarks", headers=create_header(OWNER_ID))
 
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"items": [], "total": 0, "page": 1, "size": 20}
 
 
def test_list_bookmarks_only_returns_current_user_bookmarks(
    client, bookmark_payload, bookmark_id
):
    other_response = client.post(
        "/bookmarks",
        headers=create_header(OTHER_USER_ID),
        json=bookmark_payload,
    )
    assert other_response.status_code == HTTPStatus.CREATED
 
    response = client.get("/bookmarks", headers=create_header(OWNER_ID))
 
    assert response.status_code == HTTPStatus.OK
    assert [bookmark["id"] for bookmark in response.json()["items"]] == [bookmark_id]
    assert response.json()["total"] == 1
 
def test_list_bookmarks_most_recent_first(client, bookmark_payload, bookmark_id):
    second_response = client.post(
        "/bookmarks",
        headers=create_header(OWNER_ID),
        json={**bookmark_payload, "target_id": 456},
    )
    assert second_response.status_code == HTTPStatus.CREATED
    second_id = second_response.json()["id"]
 
    response = client.get("/bookmarks", headers=create_header(OWNER_ID))
 
    assert response.status_code == HTTPStatus.OK
    assert [bookmark["id"] for bookmark in response.json()["items"]] == [second_id, bookmark_id] 

 
def test_list_bookmarks_unauthorized(client):
    response = client.get("/bookmarks")
 
    assert response.status_code == HTTPStatus.UNAUTHORIZED
 
 
def test_get_bookmark_success(client, bookmark_payload, bookmark_id):
    response = client.get(
        f"/bookmarks/{bookmark_id}", headers=create_header(OWNER_ID)
    )
 
    assert response.status_code == HTTPStatus.OK
    response_json = response.json()
    assert response_json["id"] == bookmark_id
    assert response_json["user_id"] == OWNER_ID
    assert {key: response_json[key] for key in bookmark_payload} == bookmark_payload
 
 
def test_get_bookmark_not_found(client):
    response = client.get("/bookmarks/999", headers=create_header(OWNER_ID))
 
    assert response.status_code == HTTPStatus.NOT_FOUND
 
 
def test_get_other_user_bookmark_not_found(client, bookmark_id):
    response = client.get(
        f"/bookmarks/{bookmark_id}", headers=create_header(OTHER_USER_ID)
    )
 
    assert response.status_code == HTTPStatus.NOT_FOUND
 
 
@pytest.mark.parametrize("invalid_id", [0, -1, LIMIT_INTEGER + 1])
def test_get_bookmark_invalid_id_unprocessable_entity(client, invalid_id):
    response = client.get(
        f"/bookmarks/{invalid_id}", headers=create_header(OWNER_ID)
    )
 
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
 
 
def test_get_bookmark_unauthorized(client, bookmark_id):
    response = client.get(f"/bookmarks/{bookmark_id}")
 
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_list_bookmarks_filter_streamer(client, bookmark_payload, bookmark_id):
    second_streamer_id = create_bookmark(client, bookmark_payload, target_id=456)
    create_bookmark(client, bookmark_payload, target_type="replay", target_id=789)

    body = list_bookmarks(client, target_type="streamer")

    assert {bookmark["target_type"] for bookmark in body["items"]} == {"streamer"}
    assert {bookmark["id"] for bookmark in body["items"]} == {bookmark_id, second_streamer_id}
    assert body["total"] == 2


def test_list_bookmarks_filter_replay(client, bookmark_payload, bookmark_id):
    replay_id = create_bookmark(client, bookmark_payload, target_type="replay", target_id=789)

    body = list_bookmarks(client, target_type="replay")

    assert [bookmark["id"] for bookmark in body["items"]] == [replay_id]
    assert body["total"] == 1


def test_list_bookmarks_second_page(client, bookmark_payload, bookmark_id):
    second_id = create_bookmark(client, bookmark_payload, target_id=456)
    create_bookmark(client, bookmark_payload, target_id=789)
    create_bookmark(client, bookmark_payload, target_id=1011)

    body = list_bookmarks(client, page=2, size=2)

    assert [bookmark["id"] for bookmark in body["items"]] == [second_id, bookmark_id]
    assert body["total"] == 4


def test_list_bookmarks_page_after_the_end(client, bookmark_id):
    body = list_bookmarks(client, page=10)

    assert body["items"] == []
    assert body["total"] == 1


def test_list_bookmarks_unknown_target_type_unprocessable_entity(client):
    response = client.get(
        "/bookmarks", headers=create_header(OWNER_ID), params={"target_type": "chaussette"}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "params", [{"size": 0}, {"size": 101}, {"page": 0}, {"page": LIMIT_INTEGER + 1}]
)
def test_list_bookmarks_invalid_pagination_unprocessable_entity(client, params):
    response = client.get("/bookmarks", headers=create_header(OWNER_ID), params=params)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY