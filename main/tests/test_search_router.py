import httpx
import pytest

from app.dependencies import get_search_client
from app.main import app

PAGE = {
    "items": [
        {
            "streamer_id": 42,
            "streamer_name": "Célèste",
            "last_title": "Speedrun any%",
            "last_game": "Celeste",
            "is_live": True,
            "live_stream_id": 7,
        }
    ],
    "total": 1,
    "page": 1,
    "size": 20,
}


def use_search(handler):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://search"
    )
    app.dependency_overrides[get_search_client] = lambda: client


def test_search_is_relayed(client):
    def handler(request):
        assert request.url.path == "/search/streamers"
        assert dict(request.url.params) == {"q": "cel", "page": "2", "size": "5"}
        return httpx.Response(200, json=PAGE)

    use_search(handler)
    response = client.get("/search/streamers", params={"q": "cel", "page": 2, "size": 5})
    assert response.status_code == 200
    assert response.json() == PAGE


def test_default_pagination_is_sent(client):
    def handler(request):
        assert dict(request.url.params) == {"q": "cel", "page": "1", "size": "20"}
        return httpx.Response(200, json=PAGE)

    use_search(handler)
    assert client.get("/search/streamers", params={"q": "cel"}).status_code == 200


def test_search_does_not_need_a_token(client):
    use_search(lambda request: httpx.Response(200, json=PAGE))
    assert client.get("/search/streamers", params={"q": "cel"}).status_code == 200


@pytest.mark.parametrize(
    "params",
    [{}, {"q": "c"}, {"q": "c" * 101}, {"q": "cel", "page": 0}, {"q": "cel", "size": 51}],
)
def test_invalid_params_are_not_relayed(client, params):
    def handler(request):
        raise AssertionError("search should not be called")

    use_search(handler)
    assert client.get("/search/streamers", params=params).status_code == 422


def test_query_refused_by_search_returns_422(client):
    detail = [{"type": "value_error", "loc": ["query", "q"], "msg": "empty"}]
    use_search(lambda request: httpx.Response(422, json={"detail": detail}))
    response = client.get("/search/streamers", params={"q": "́́"})
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "answer",
    [httpx.Response(500), httpx.Response(200, json={"items": "nope"}), httpx.Response(422)],
)
def test_unexpected_answer_returns_502(client, answer):
    use_search(lambda request: answer)
    assert client.get("/search/streamers", params={"q": "cel"}).status_code == 502


def test_search_down_returns_503(client):
    def handler(request):
        raise httpx.ConnectError("refused")

    use_search(handler)
    assert client.get("/search/streamers", params={"q": "cel"}).status_code == 503


def test_search_timeout_returns_504(client):
    def handler(request):
        raise httpx.ReadTimeout("too slow")

    use_search(handler)
    assert client.get("/search/streamers", params={"q": "cel"}).status_code == 504


def test_route_is_documented(client):
    operation = client.get("/openapi.json").json()["paths"]["/search/streamers"]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema == {"$ref": "#/components/schemas/StreamerPage"}
