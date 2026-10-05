import pytest

from app import conversion
from app.infra.db import get_session
from app.infra.models import Mp4Status
from app.main import app
from tests.factories import add_replay, reload

DOWNLOAD_URL = "/replays/42/download"


def assert_pending(response):
    assert response.status_code == 202
    assert response.json() == {"stream_id": 42, "mp4_status": "processing"}
    assert response.headers["retry-after"] == "5"


@pytest.mark.anyio
async def test_unknown_replay_returns_404(client, fake_ffmpeg):
    response = await client.get(DOWNLOAD_URL)

    assert response.status_code == 404
    assert response.json() == {"detail": "Replay not found"}
    assert fake_ffmpeg.calls == []


@pytest.mark.anyio
async def test_live_in_progress_returns_404(client, session, fake_ffmpeg):
    await add_replay(session, 42, ended_at=None, duration_s=None)

    response = await client.get(DOWNLOAD_URL)

    assert response.status_code == 404
    assert fake_ffmpeg.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "stream_id", ["abc", "0", "2147483648"], ids=["text", "zero", "above-int32"]
)
async def test_invalid_stream_id_returns_422(client, fake_ffmpeg, stream_id):
    response = await client.get(f"/replays/{stream_id}/download")

    assert response.status_code == 422
    assert fake_ffmpeg.calls == []


@pytest.mark.anyio
async def test_first_download_starts_the_conversion_and_returns_202(client, session, fake_ffmpeg):
    await add_replay(session, 42)

    response = await client.get(DOWNLOAD_URL)

    assert_pending(response)
    # ASGITransport attend les tâches de fond : la conversion est finie ici.
    assert len(fake_ffmpeg.calls) == 1
    assert (await reload(session, 42)).mp4_status is Mp4Status.READY


@pytest.mark.anyio
async def test_download_after_the_conversion_returns_the_file(client, session, fake_ffmpeg):
    await add_replay(session, 42)
    await client.get(DOWNLOAD_URL)

    response = await client.get(DOWNLOAD_URL)

    assert response.status_code == 200
    # Contenu écrit par le faux ffmpeg dans le .part, puis renommé.
    assert response.content == b"partial mp4"
    assert len(fake_ffmpeg.calls) == 1


@pytest.mark.anyio
async def test_processing_returns_202_without_a_second_ffmpeg(client, session, fake_ffmpeg):
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)

    response = await client.get(DOWNLOAD_URL)

    assert_pending(response)
    assert fake_ffmpeg.calls == []


@pytest.mark.anyio
async def test_ready_returns_the_file_as_an_attachment(client, session, converter, fake_ffmpeg):
    await add_replay(session, 42, mp4_status=Mp4Status.READY)
    converter.mp4_path(42).write_bytes(b"mp4 bytes")

    response = await client.get(DOWNLOAD_URL)

    assert response.status_code == 200
    assert response.content == b"mp4 bytes"
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-disposition"] == 'attachment; filename="replay-42.mp4"'
    assert fake_ffmpeg.calls == []


@pytest.mark.anyio
async def test_ready_without_file_converts_again(client, session, fake_ffmpeg):
    await add_replay(session, 42, mp4_status=Mp4Status.READY)

    response = await client.get(DOWNLOAD_URL)

    assert_pending(response)
    assert len(fake_ffmpeg.calls) == 1


@pytest.mark.anyio
async def test_failed_returns_500_once_then_converts_again(client, session, fake_ffmpeg):
    await add_replay(session, 42, mp4_status=Mp4Status.FAILED)

    first_response = await client.get(DOWNLOAD_URL)

    assert first_response.status_code == 500
    assert first_response.json() == {"detail": "Conversion failed, try again"}
    assert (await reload(session, 42)).mp4_status is Mp4Status.NONE
    assert fake_ffmpeg.calls == []

    second_response = await client.get(DOWNLOAD_URL)

    assert_pending(second_response)
    assert len(fake_ffmpeg.calls) == 1


@pytest.mark.anyio
async def test_failed_conversion_is_reported_on_the_next_download(client, session, fake_ffmpeg):
    await add_replay(session, 42)
    fake_ffmpeg.returncode = 1

    assert_pending(await client.get(DOWNLOAD_URL))
    response = await client.get(DOWNLOAD_URL)

    assert response.status_code == 500


@pytest.mark.anyio
async def test_session_is_closed_before_converting(client, session, fake_ffmpeg, monkeypatch):
    await add_replay(session, 42)
    session_state = {"closed": False}
    closed_when_converting = []

    async def tracked_get_session():
        yield session
        session_state["closed"] = True

    async def tracked_ffmpeg(*args, **kwargs):
        closed_when_converting.append(session_state["closed"])
        return await fake_ffmpeg(*args, **kwargs)

    # Remplace l'override de la fixture client, vidé à la fin du test.
    app.dependency_overrides[get_session] = tracked_get_session
    monkeypatch.setattr(conversion.asyncio, "create_subprocess_exec", tracked_ffmpeg)

    await client.get(DOWNLOAD_URL)

    assert closed_when_converting == [True]
