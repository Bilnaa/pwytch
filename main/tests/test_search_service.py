import httpx
import pytest

from app.services.search import (
    InvalidSearchQueryError,
    InvalidSearchResponseError,
    SearchTimeoutError,
    SearchUnavailableError,
    search_streamers,
)

pytestmark = pytest.mark.anyio

PAGE = {
    "items": [
        {
            "streamer_id": 42,
            "streamer_name": "alice",
            "last_title": None,
            "last_game": None,
            "is_live": False,
            "live_stream_id": None,
        }
    ],
    "total": 1,
    "page": 1,
    "size": 20,
}


def search_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://search")


async def test_search_streamers_returns_the_page():
    def handler(request):
        assert request.url.path == "/search/streamers"
        assert dict(request.url.params) == {"q": "ali", "page": "1", "size": "20"}
        return httpx.Response(200, json=PAGE)

    async with search_client(handler) as client:
        page = await search_streamers(client, "ali", 1, 20)

    assert page.model_dump() == PAGE


async def test_search_streamers_keeps_the_422_detail():
    detail = [{"msg": "empty"}]

    async with search_client(lambda request: httpx.Response(422, json={"detail": detail})) as client:
        with pytest.raises(InvalidSearchQueryError) as exc_info:
            await search_streamers(client, "ali", 1, 20)

    assert exc_info.value.detail == detail


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(500),
        httpx.Response(404),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json={"items": []}),
        httpx.Response(422, content=b"not json"),
    ],
)
async def test_search_streamers_rejects_bad_answers(answer):
    async with search_client(lambda request: answer) as client:
        with pytest.raises(InvalidSearchResponseError):
            await search_streamers(client, "ali", 1, 20)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (httpx.ConnectError("refused"), SearchUnavailableError),
        (httpx.ReadTimeout("too slow"), SearchTimeoutError),
    ],
)
async def test_search_streamers_wraps_transport_errors(exception, error):
    def handler(request):
        raise exception

    async with search_client(handler) as client:
        with pytest.raises(error):
            await search_streamers(client, "ali", 1, 20)
