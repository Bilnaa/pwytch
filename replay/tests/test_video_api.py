import pytest

from app.models import Mp4Status
from tests.factories import add_replay

VIDEO_URL = "/replays/42/video"


@pytest.mark.anyio
async def test_ready_replay_is_served_inline(client, session, tmp_path, fake_ffmpeg):
    await add_replay(session, 42, mp4_status=Mp4Status.READY)
    (tmp_path / "42.mp4").write_bytes(b"0123456789")

    response = await client.get(VIDEO_URL)

    assert response.status_code == 200
    assert response.content == b"0123456789"
    assert response.headers["content-type"] == "video/mp4"
    assert "attachment" not in response.headers.get("content-disposition", "")
    assert fake_ffmpeg.calls == []


@pytest.mark.anyio
async def test_range_request_returns_206_with_the_part(client, session, tmp_path):
    await add_replay(session, 42, mp4_status=Mp4Status.READY)
    (tmp_path / "42.mp4").write_bytes(b"0123456789")

    response = await client.get(VIDEO_URL, headers={"Range": "bytes=2-5"})

    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/10"


@pytest.mark.anyio
@pytest.mark.parametrize("status", [Mp4Status.NONE, Mp4Status.PROCESSING, Mp4Status.FAILED])
async def test_video_not_ready_returns_404_without_conversion(client, session, fake_ffmpeg, status):
    await add_replay(session, 42, mp4_status=status)

    response = await client.get(VIDEO_URL)

    assert response.status_code == 404
    assert response.json() == {"detail": "Replay video not ready"}
    assert fake_ffmpeg.calls == []


@pytest.mark.anyio
async def test_ready_replay_with_missing_file_returns_404(client, session):
    await add_replay(session, 42, mp4_status=Mp4Status.READY)

    response = await client.get(VIDEO_URL)

    assert response.status_code == 404


@pytest.mark.anyio
async def test_unknown_replay_returns_404(client):
    response = await client.get(VIDEO_URL)

    assert response.json() == {"detail": "Replay not found"}
