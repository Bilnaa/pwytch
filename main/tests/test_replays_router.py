import anyio
import httpx
import pytest

from app.config import replay_settings
from app.dependencies import get_replay_client
from app.main import app

REPLAY = {
    "stream_id": 7,
    "streamer_id": 42,
    "streamer_name": "Célèste",
    "title": "Speedrun any%",
    "game": "Celeste",
    "started_at": "2026-10-02T19:00:00Z",
    "ended_at": "2026-10-02T20:02:05Z",
    "duration_s": 3725.4,
    "mp4_status": "none",
    "playback_url": "/replays/7/video",
}
PAGE = {"items": [REPLAY], "total": 1, "page": 1, "size": 20}


@pytest.fixture
def use_replay():
    clients = []

    def use(handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://replay")
        clients.append(client)
        app.dependency_overrides[get_replay_client] = lambda: client

    yield use
    for client in clients:
        anyio.run(client.aclose)


def test_list_is_relayed_with_default_page(client, use_replay):
    def handler(request):
        assert request.url.path == "/replays"
        assert dict(request.url.params) == {"page": "1", "size": "20"}
        return httpx.Response(200, json=PAGE)

    use_replay(handler)
    response = client.get("/replays")
    assert response.status_code == 200
    assert response.json() == PAGE


def test_list_relays_page_size_and_streamer(client, use_replay):
    def handler(request):
        assert dict(request.url.params) == {"page": "2", "size": "5", "streamer_id": "42"}
        return httpx.Response(200, json={**PAGE, "page": 2, "size": 5})

    use_replay(handler)
    response = client.get("/replays", params={"page": 2, "size": 5, "streamer_id": 42})
    assert response.status_code == 200
    assert response.json()["page"] == 2


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": 2_147_483_648},
        {"size": 0},
        {"size": 51},
        {"streamer_id": 0},
        {"page": "x"},
    ],
)
def test_invalid_list_params_are_not_relayed(client, use_replay, params):
    def handler(request):
        raise AssertionError("replay should not be called")

    use_replay(handler)
    assert client.get("/replays", params=params).status_code == 422


def test_one_replay_is_relayed(client, use_replay):
    def handler(request):
        assert request.url.path == "/replays/7"
        return httpx.Response(200, json=REPLAY)

    use_replay(handler)
    response = client.get("/replays/7")
    assert response.status_code == 200
    assert response.json() == REPLAY


def test_unknown_replay_404_is_relayed(client, use_replay):
    use_replay(lambda request: httpx.Response(404, json={"detail": "Replay not found"}))
    response = client.get("/replays/7")
    assert response.status_code == 404
    assert response.json() == {"detail": "Replay not found"}


@pytest.mark.parametrize("stream_id", ["0", "2147483648", "abc"])
def test_invalid_replay_id_is_not_relayed(client, use_replay, stream_id):
    def handler(request):
        raise AssertionError("replay should not be called")

    use_replay(handler)
    assert client.get(f"/replays/{stream_id}").status_code == 422


@pytest.mark.parametrize(
    ("failure", "status_code"),
    [
        (httpx.Response(500), 502),
        (httpx.Response(200, json={"items": "nope"}), 502),
        (httpx.ConnectError("refused"), 503),
        (httpx.ReadTimeout("too slow"), 504),
    ],
)
def test_replay_failures_are_mapped(client, use_replay, failure, status_code):
    def handler(request):
        if isinstance(failure, Exception):
            raise failure
        return failure

    use_replay(handler)
    assert client.get("/replays").status_code == status_code
    assert client.get("/replays/7").status_code == status_code


def test_routes_do_not_need_a_token(client, use_replay):
    def handler(request):
        return httpx.Response(200, json=PAGE if request.url.path == "/replays" else REPLAY)

    use_replay(handler)
    assert client.get("/replays").status_code == 200
    assert client.get("/replays/7").status_code == 200


def test_routes_are_documented(client):
    paths = client.get("/openapi.json").json()["paths"]
    many = paths["/api/replays"]["get"]["responses"]
    one = paths["/api/replays/{stream_id}"]["get"]["responses"]
    assert many["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReplayPage"
    }
    assert one["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReplayResponse"
    }
    assert "404" in one


def test_download_is_streamed_with_replay_headers(client, use_replay):
    def handler(request):
        assert request.url.path == "/replays/7/download"
        return httpx.Response(
            200,
            content=b"mp4-bytes",
            headers={
                "content-type": "video/mp4",
                "content-disposition": 'attachment; filename="replay-7.mp4"',
            },
        )

    use_replay(handler)
    response = client.get("/replays/7/download")
    assert response.status_code == 200
    assert response.content == b"mp4-bytes"
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-disposition"] == 'attachment; filename="replay-7.mp4"'


def test_download_pending_conversion_is_relayed_as_is(client, use_replay):
    pending = {"stream_id": 7, "mp4_status": "processing"}
    use_replay(lambda request: httpx.Response(202, json=pending, headers={"retry-after": "5"}))
    response = client.get("/replays/7/download")
    assert response.status_code == 202
    assert response.json() == pending
    assert response.headers["retry-after"] == "5"


def test_download_uses_its_own_timeout(client, use_replay, monkeypatch):
    monkeypatch.setattr(replay_settings, "replay_timeout_seconds", 4)
    monkeypatch.setattr(replay_settings, "replay_download_timeout_seconds", 123)

    def handler(request):
        assert request.extensions["timeout"] == {
            "connect": 4,
            "read": 123,
            "write": 4,
            "pool": 4,
        }
        return httpx.Response(200, content=b"", headers={"content-type": "video/mp4"})

    use_replay(handler)
    assert client.get("/replays/7/download").status_code == 200


def test_download_unknown_replay_404_is_relayed(client, use_replay):
    use_replay(lambda request: httpx.Response(404, json={"detail": "Replay not found"}))
    response = client.get("/replays/7/download")
    assert response.status_code == 404
    assert response.json() == {"detail": "Replay not found"}


@pytest.mark.parametrize(
    ("failure", "status_code"),
    [
        (httpx.Response(503), 502),
        (httpx.ConnectError("refused"), 503),
        (httpx.ReadTimeout("too slow"), 504),
    ],
)
def test_download_failures_are_mapped(client, use_replay, failure, status_code):
    def handler(request):
        if isinstance(failure, Exception):
            raise failure
        return failure

    use_replay(handler)
    assert client.get("/replays/7/download").status_code == status_code


def test_download_failed_conversion_500_is_relayed(client, use_replay):
    failed = {"detail": "Conversion failed, try again"}
    use_replay(lambda request: httpx.Response(500, json=failed))
    response = client.get("/replays/7/download")
    assert response.status_code == 500
    assert response.json() == failed


@pytest.mark.parametrize("stream_id", ["0", "2147483648", "abc"])
def test_invalid_download_id_is_not_relayed(client, use_replay, stream_id):
    def handler(request):
        raise AssertionError("replay should not be called")

    use_replay(handler)
    assert client.get(f"/replays/{stream_id}/download").status_code == 422


def test_video_range_is_forwarded_and_206_relayed(client, use_replay):
    def handler(request):
        assert request.url.path == "/replays/7/video"
        assert request.headers["range"] == "bytes=2-5"
        return httpx.Response(
            206,
            content=b"2345",
            headers={
                "content-type": "video/mp4",
                "content-range": "bytes 2-5/10",
                "accept-ranges": "bytes",
            },
        )

    use_replay(handler)
    response = client.get("/replays/7/video", headers={"Range": "bytes=2-5"})
    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.headers["accept-ranges"] == "bytes"


def test_video_without_range_sends_no_range(client, use_replay):
    def handler(request):
        assert "range" not in request.headers
        return httpx.Response(200, content=b"mp4", headers={"content-type": "video/mp4"})

    use_replay(handler)
    assert client.get("/replays/7/video").status_code == 200


def test_video_not_ready_404_is_relayed(client, use_replay):
    not_ready = {"detail": "Replay video not ready"}
    use_replay(lambda request: httpx.Response(404, json=not_ready))
    response = client.get("/replays/7/video")
    assert response.status_code == 404
    assert response.json() == not_ready
