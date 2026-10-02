import httpx
import pytest

from app.main import app
from app.dependencies import get_stream_client


def use_stream(handler):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://stream"
    )
    app.dependency_overrides[get_stream_client] = lambda: client


def test_playlist_is_relayed_without_cache(client):
    def handler(request):
        assert request.url.path == "/lives/3/index.m3u8"
        return httpx.Response(
            200, content=b"#EXTM3U", headers={"content-type": "application/vnd.apple.mpegurl"}
        )

    use_stream(handler)
    response = client.get("/lives/3/index.m3u8")
    assert response.status_code == 200
    assert response.content == b"#EXTM3U"
    assert response.headers["content-type"] == "application/vnd.apple.mpegurl"
    assert response.headers["cache-control"] == "no-cache"


def test_segment_can_be_cached(client):
    use_stream(
        lambda request: httpx.Response(
            200, content=b"\x00\x01", headers={"content-type": "video/mp2t"}
        )
    )
    response = client.get("/lives/3/index12.ts")
    assert response.status_code == 200
    assert response.content == b"\x00\x01"
    assert response.headers["content-type"] == "video/mp2t"
    assert "max-age" in response.headers["cache-control"]


def test_missing_file_returns_404(client):
    use_stream(lambda request: httpx.Response(404))
    assert client.get("/lives/3/index.m3u8").status_code == 404


def test_unexpected_status_returns_502(client):
    use_stream(lambda request: httpx.Response(500))
    assert client.get("/lives/3/index.m3u8").status_code == 502


@pytest.mark.parametrize("filename", ["index.mp4", "playlist.m3u8", "index.ts.exe"])
def test_invalid_filename_returns_422(client, filename):
    use_stream(lambda request: httpx.Response(200))
    assert client.get(f"/lives/3/{filename}").status_code == 422


def test_path_traversal_is_not_relayed(client):
    use_stream(lambda request: httpx.Response(200))
    assert client.get("/lives/3/..%2Fsecret.m3u8").status_code in (404, 422)


def test_invalid_stream_id_returns_422(client):
    use_stream(lambda request: httpx.Response(200))
    assert client.get("/lives/abc/index.m3u8").status_code == 422


def test_stream_down_returns_503(client):
    def handler(request):
        raise httpx.ConnectError("refused")

    use_stream(handler)
    assert client.get("/lives/3/index.m3u8").status_code == 503


def test_stream_timeout_returns_504(client):
    def handler(request):
        raise httpx.ReadTimeout("too slow")

    use_stream(handler)
    assert client.get("/lives/3/index.m3u8").status_code == 504
