import anyio
import httpx
import pytest

from app.dependencies import get_search_client
from app.main import app

STREAMER = {
    "streamer_id": 42,
    "streamer_name": "Célèste",
    "last_title": "Speedrun any%",
    "last_game": "Celeste",
    "is_live": True,
    "live_stream_id": 7,
}
MESSAGE = {
    "message_id": "3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97",
    "stream_id": 7,
    "author_name": "Célèste",
    "content": "GG WP !",
    "sent_at": "2026-10-02T20:14:03Z",
}


def answer(request):
    if request.url.path == "/search/streamers":
        return httpx.Response(200, json={"items": [STREAMER], "total": 1, "page": 1, "size": 20})
    return httpx.Response(200, json=[MESSAGE])


@pytest.fixture
def use_search():
    clients = []

    def use(handler):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://search"
        )
        clients.append(client)
        app.dependency_overrides[get_search_client] = lambda: client

    yield use
    for client in clients:
        anyio.run(client.aclose)


def test_both_sections_are_returned(client, use_search):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert dict(request.url.params) == {"q": "gg"}
        return answer(request)

    use_search(handler)
    response = client.get("/search", params={"q": " gg "})
    assert response.status_code == 200
    assert response.json() == {"streamers": [STREAMER], "messages": [MESSAGE]}
    assert sorted(paths) == ["/search/messages", "/search/streamers"]


def test_messages_route_missing_in_search_gives_empty_messages(client, use_search):
    def handler(request):
        if request.url.path == "/search/messages":
            return httpx.Response(404, json={"detail": "Not Found"})
        return answer(request)

    use_search(handler)
    response = client.get("/search", params={"q": "gg"})
    assert response.status_code == 200
    assert response.json() == {"streamers": [STREAMER], "messages": []}


def test_search_does_not_need_a_token(client, use_search):
    use_search(answer)
    assert client.get("/search", params={"q": "gg"}).status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": "g"},
        {"q": "g" * 101},
        {"q": "  "},
        {"q": " g "},
    ],
)
def test_invalid_params_are_not_relayed(client, use_search, params):
    def handler(request):
        raise AssertionError("search should not be called")

    use_search(handler)
    assert client.get("/search", params=params).status_code == 422


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(500),
        httpx.Response(422, json={"detail": []}),
        httpx.Response(200, json={"items": "nope"}),
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("too slow"),
    ],
)
def test_failed_streamers_section_is_empty(client, use_search, failure):
    def handler(request):
        if request.url.path == "/search/streamers":
            if isinstance(failure, Exception):
                raise failure
            return failure
        return answer(request)

    use_search(handler)
    response = client.get("/search", params={"q": "gg"})
    assert response.status_code == 200
    assert response.json() == {"streamers": [], "messages": [MESSAGE]}


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(500),
        httpx.Response(200, json=[{"content": "no id"}]),
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("too slow"),
    ],
)
def test_failed_messages_section_is_empty(client, use_search, failure):
    def handler(request):
        if request.url.path != "/search/streamers":
            if isinstance(failure, Exception):
                raise failure
            return failure
        return answer(request)

    use_search(handler)
    response = client.get("/search", params={"q": "gg"})
    assert response.status_code == 200
    assert response.json() == {"streamers": [STREAMER], "messages": []}


def test_search_down_returns_empty_sections(client, use_search):
    def handler(request):
        raise httpx.ConnectError("refused")

    use_search(handler)
    response = client.get("/search", params={"q": "gg"})
    assert response.status_code == 200
    assert response.json() == {"streamers": [], "messages": []}


def test_route_is_documented(client):
    operation = client.get("/openapi.json").json()["paths"]["/api/search"]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/SearchResults"}
