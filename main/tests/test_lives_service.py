import httpx
import pytest

from app.services.lives import (
    InvalidStreamResponseError,
    LiveFileNotFoundError,
    StreamTimeoutError,
    StreamUnavailableError,
    get_cache_control,
    open_live_file,
)

pytestmark = pytest.mark.anyio


def stream_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://stream")


def test_playlist_is_not_cached():
    assert get_cache_control("index.m3u8") == "no-cache"


def test_segment_is_cached():
    assert "max-age" in get_cache_control("index12.ts")


async def test_open_live_file_relays_content():
    def handler(request):
        assert request.url.path == "/lives/3/index.m3u8"
        return httpx.Response(
            200, content=b"#EXTM3U", headers={"content-type": "application/vnd.apple.mpegurl"}
        )

    async with stream_client(handler) as client:
        live_file = await open_live_file(client, 3, "index.m3u8")
        content = b"".join([chunk async for chunk in live_file.content])
        await live_file.close()

    assert content == b"#EXTM3U"
    assert live_file.media_type == "application/vnd.apple.mpegurl"
    assert live_file.cache_control == "no-cache"


@pytest.mark.parametrize(
    ("handler", "error"),
    [
        (lambda request: httpx.Response(404), LiveFileNotFoundError),
        (lambda request: httpx.Response(500), InvalidStreamResponseError),
    ],
)
async def test_open_live_file_rejects_bad_status(handler, error):
    async with stream_client(handler) as client:
        with pytest.raises(error):
            await open_live_file(client, 3, "index.m3u8")


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (httpx.ConnectError("refused"), StreamUnavailableError),
        (httpx.ReadTimeout("too slow"), StreamTimeoutError),
    ],
)
async def test_open_live_file_wraps_transport_errors(exception, error):
    def handler(request):
        raise exception

    async with stream_client(handler) as client:
        with pytest.raises(error):
            await open_live_file(client, 3, "index.m3u8")
