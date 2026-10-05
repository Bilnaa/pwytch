import anyio
import httpx
import pytest

from app.dependencies import get_live_chat_client
from app.main import app
from tests.fakes import create_stream

MESSAGE = {
    "id": "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b",
    "stream_id": 1,
    "author": {"id": 42, "username": "Célèste"},
    "content": "GG WP !",
    "sent_at": "2026-10-02T19:00:00Z",
}


@pytest.fixture
def use_live_chat():
    clients = []

    def use(handler):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://live-chat"
        )
        clients.append(client)
        app.dependency_overrides[get_live_chat_client] = lambda: client

    yield use
    for client in clients:
        anyio.run(client.aclose)


def test_messages_are_relayed_with_default_limit(client, use_live_chat):
    stream_id, _ = create_stream(client)

    def handler(request):
        assert request.url.path == f"/streams/{stream_id}/messages"
        assert dict(request.url.params) == {"limit": "50"}
        return httpx.Response(200, json=[{**MESSAGE, "stream_id": stream_id}])

    use_live_chat(handler)
    response = client.get(f"/streams/{stream_id}/messages")
    assert response.status_code == 200
    assert response.json() == [{**MESSAGE, "stream_id": stream_id}]


def test_limit_is_relayed(client, use_live_chat):
    stream_id, _ = create_stream(client)

    def handler(request):
        assert dict(request.url.params) == {"limit": "10"}
        return httpx.Response(200, json=[])

    use_live_chat(handler)
    response = client.get(f"/streams/{stream_id}/messages", params={"limit": 10})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("limit", ["0", "101", "x"])
def test_invalid_limit_is_not_relayed(client, use_live_chat, limit):
    stream_id, _ = create_stream(client)

    def handler(request):
        raise AssertionError("live-chat should not be called")

    use_live_chat(handler)
    response = client.get(f"/streams/{stream_id}/messages", params={"limit": limit})
    assert response.status_code == 422


def test_unknown_stream_is_404_without_calling_live_chat(client, use_live_chat):
    def handler(request):
        raise AssertionError("live-chat should not be called")

    use_live_chat(handler)
    response = client.get("/streams/999/messages")
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("failure", "status_code"),
    [
        (httpx.Response(503), 502),
        (httpx.Response(200, json=[{"id": "nope"}]), 502),
        (httpx.ConnectError("refused"), 503),
        (httpx.ReadTimeout("too slow"), 504),
    ],
)
def test_live_chat_failures_are_mapped(client, use_live_chat, failure, status_code):
    stream_id, _ = create_stream(client)

    def handler(request):
        if isinstance(failure, Exception):
            raise failure
        return failure

    use_live_chat(handler)
    assert client.get(f"/streams/{stream_id}/messages").status_code == status_code


def test_route_is_documented(client):
    paths = client.get("/openapi.json").json()["paths"]
    responses = paths["/api/streams/{stream_id}/messages"]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/ChatMessage"},
        "title": "Response Get Messages Api Streams  Stream Id  Messages Get",
    }
    assert {"404", "422", "502", "503", "504"} <= responses.keys()
