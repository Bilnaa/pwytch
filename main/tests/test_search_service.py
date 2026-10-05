import httpx
import pytest

from app.services.satellites import SatelliteError
from app.services.search import search_all, search_messages, search_streamers

pytestmark = pytest.mark.anyio

STREAMER = {
    "streamer_id": 42,
    "streamer_name": "alice",
    "last_title": None,
    "last_game": None,
    "is_live": False,
    "live_stream_id": None,
}
MESSAGE = {
    "message_id": "3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97",
    "stream_id": 7,
    "author_name": "alice",
    "content": "GG WP !",
    "sent_at": "2026-10-02T20:14:03Z",
}


def search_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://search")


async def test_search_streamers_returns_the_items():
    def handler(request):
        assert request.url.path == "/search/streamers"
        assert dict(request.url.params) == {"q": "ali"}
        return httpx.Response(200, json={"items": [STREAMER], "total": 1, "page": 1, "size": 20})

    async with search_client(handler) as client:
        streamers = await search_streamers(client, "ali")

    assert [streamer.model_dump() for streamer in streamers] == [STREAMER]


async def test_search_messages_calls_the_global_route():
    def handler(request):
        assert request.url.path == "/search/messages"
        assert dict(request.url.params) == {"q": "gg"}
        return httpx.Response(200, json=[MESSAGE])

    async with search_client(handler) as client:
        messages = await search_messages(client, "gg")

    assert [message.model_dump(mode="json") for message in messages] == [MESSAGE]


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500),
        lambda request: httpx.Response(422, json={"detail": []}),
        lambda request: httpx.Response(200, content=b"not json"),
        lambda request: httpx.Response(200, json={"items": []}),
    ],
)
async def test_search_streamers_rejects_bad_answers(handler):
    async with search_client(handler) as client:
        with pytest.raises(SatelliteError):
            await search_streamers(client, "ali")


@pytest.mark.parametrize(
    "exception", [httpx.ConnectError("refused"), httpx.ReadTimeout("too slow")]
)
async def test_transport_errors_are_raised(exception):
    def handler(request):
        raise exception

    async with search_client(handler) as client:
        with pytest.raises(SatelliteError):
            await search_streamers(client, "ali")


async def test_search_all_keeps_the_section_that_answered():
    def handler(request):
        if request.url.path == "/search/streamers":
            raise httpx.ReadTimeout("too slow")
        return httpx.Response(200, json=[MESSAGE])

    async with search_client(handler) as client:
        results = await search_all(client, "gg")

    assert results.streamers == []
    assert len(results.messages) == 1
