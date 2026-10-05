import json

import anyio
import httpx
import pytest

from app.dependencies import get_bookmarks_client
from app.main import app
from tests.test_streams_router import auth_headers

BOOKMARK = {
    "id": 3,
    "user_id": 1,
    "target_type": "replay",
    "target_id": 7,
    "label": "Run record",
    "note": None,
    "created_at": "2026-10-02T20:14:03Z",
    "updated_at": "2026-10-02T20:14:03Z",
}
CREATE = {"target_type": "replay", "target_id": 7, "label": "Run record"}
PAGE = {"items": [BOOKMARK], "total": 1, "page": 1, "size": 20}


@pytest.fixture
def use_bookmarks():
    clients = []

    def use(handler):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://bookmarks"
        )
        clients.append(client)
        app.dependency_overrides[get_bookmarks_client] = lambda: client

    yield use
    for client in clients:
        anyio.run(client.aclose)


@pytest.fixture
def recorded(use_bookmarks):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "POST":
            return httpx.Response(201, json=BOOKMARK, headers={"Location": "/bookmarks/3"})
        if request.url.path == "/bookmarks":
            return httpx.Response(200, json=PAGE)
        return httpx.Response(200, json=BOOKMARK)

    use_bookmarks(handler)
    return requests


ROUTES = [
    ("GET", "/bookmarks", None),
    ("POST", "/bookmarks", CREATE),
    ("GET", "/bookmarks/3", None),
    ("PATCH", "/bookmarks/3", {"label": "Autre"}),
    ("DELETE", "/bookmarks/3", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_routes_require_a_token(client, recorded, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 401
    assert recorded == []


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_routes_send_the_identity(client, recorded, method, path, body):
    client.request(method, path, json=body, headers=auth_headers(client))
    request = recorded[0]
    assert (request.method, request.url.path) == (method, path)
    assert request.headers["X-User-Name"] == "alice"
    assert request.headers["X-User-Id"].isdigit()


def test_list_returns_the_page_with_default_params(client, recorded):
    response = client.get("/bookmarks", headers=auth_headers(client))
    assert response.status_code == 200
    assert response.json() == PAGE
    assert dict(recorded[0].url.params) == {"page": "1", "size": "20"}


def test_list_relays_page_size_and_target_type(client, recorded):
    client.get(
        "/bookmarks",
        params={"page": 2, "size": 5, "target_type": "streamer"},
        headers=auth_headers(client),
    )
    assert dict(recorded[0].url.params) == {"page": "2", "size": "5", "target_type": "streamer"}


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": 2_147_483_648},
        {"size": 0},
        {"size": 101},
        {"target_type": "game"},
    ],
)
def test_invalid_list_params_are_not_relayed(client, recorded, params):
    response = client.get("/bookmarks", params=params, headers=auth_headers(client))
    assert response.status_code == 422
    assert recorded == []


def test_create_returns_201_with_location(client, recorded):
    response = client.post("/bookmarks", json=CREATE, headers=auth_headers(client))
    assert response.status_code == 201
    assert response.headers["Location"] == "/api/bookmarks/3"
    assert response.json() == BOOKMARK
    assert json.loads(recorded[0].content) == {**CREATE, "note": None}


def test_get_returns_the_bookmark(client, recorded):
    response = client.get("/bookmarks/3", headers=auth_headers(client))
    assert response.status_code == 200
    assert response.json() == BOOKMARK


@pytest.mark.parametrize("bookmark_id", [0, 2_147_483_648])
def test_invalid_bookmark_id_is_not_relayed(client, recorded, bookmark_id):
    response = client.get(f"/bookmarks/{bookmark_id}", headers=auth_headers(client))
    assert response.status_code == 422
    assert recorded == []


def test_update_only_sends_the_given_fields(client, recorded):
    response = client.patch("/bookmarks/3", json={"note": "GG"}, headers=auth_headers(client))
    assert response.status_code == 200
    assert json.loads(recorded[0].content) == {"note": "GG"}


def test_delete_returns_204(client, recorded):
    response = client.delete("/bookmarks/3", headers=auth_headers(client))
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.parametrize(
    "body",
    [
        {"target_type": "game", "target_id": 7, "label": "Run"},
        {"target_type": "replay", "label": "Run"},
        {**CREATE, "user_id": 2},
    ],
)
def test_invalid_create_is_not_relayed(client, recorded, body):
    response = client.post("/bookmarks", json=body, headers=auth_headers(client))
    assert response.status_code == 422
    assert recorded == []


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (httpx.Response(404, json={"detail": "bookmark not found"}), 404),
        (httpx.Response(409, json={"detail": "bookmark already exists"}), 409),
        (httpx.Response(422, json={"detail": []}), 422),
    ],
)
def test_rejection_is_relayed(client, use_bookmarks, answer, code):
    use_bookmarks(lambda request: answer)
    response = client.post("/bookmarks", json=CREATE, headers=auth_headers(client))
    assert response.status_code == code
    assert response.content == answer.content


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (httpx.Response(500), 502),
        (httpx.Response(200, json={"id": "nope"}), 502),
        (httpx.ConnectError("refused"), 503),
        (httpx.ReadTimeout("too slow"), 504),
    ],
)
def test_bookmarks_failure(client, use_bookmarks, failure, code):
    def handler(request):
        if isinstance(failure, Exception):
            raise failure
        return failure

    use_bookmarks(handler)
    assert client.get("/bookmarks/3", headers=auth_headers(client)).status_code == code


def test_routes_are_documented(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/api/bookmarks"]) == {"get", "post"}
    assert set(paths["/api/bookmarks/{bookmark_id}"]) == {"get", "patch", "delete"}
    listed = paths["/api/bookmarks"]["get"]["responses"]["200"]
    assert listed["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Page_BookmarkResponse_"
    }
    created = paths["/api/bookmarks"]["post"]["responses"]["201"]
    assert created["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/BookmarkResponse"
    }
    assert "204" in paths["/api/bookmarks/{bookmark_id}"]["delete"]["responses"]
