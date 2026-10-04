import httpx
import pytest

from app.services.lives import get_cache_control, open_live_file
from app.services.satellites import SatelliteRejectedError

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


async def test_open_live_file_rejects_missing_file():
    async with stream_client(lambda request: httpx.Response(404)) as client:
        with pytest.raises(SatelliteRejectedError):
            await open_live_file(client, 3, "index.m3u8")
