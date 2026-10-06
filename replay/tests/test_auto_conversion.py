import asyncio

import pytest

from app.models import Mp4Status
from tests.factories import add_replay, reload, write_playlist


async def wait_conversions(converter):
    await asyncio.gather(*converter.tasks)


@pytest.mark.anyio
async def test_start_converts_a_finished_replay(converter, fake_ffmpeg, session, lives_dir):
    await add_replay(session, 42)
    write_playlist(lives_dir, 42)

    await converter.start(42)
    await wait_conversions(converter)

    assert len(fake_ffmpeg.calls) == 1
    assert (await reload(session, 42)).mp4_status is Mp4Status.READY


@pytest.mark.anyio
async def test_start_skips_a_live_still_in_progress(converter, fake_ffmpeg, session, lives_dir):
    await add_replay(session, 42, ended_at=None, duration_s=None)
    write_playlist(lives_dir, 42)

    await converter.start(42)

    assert fake_ffmpeg.calls == []
    assert (await reload(session, 42)).mp4_status is Mp4Status.NONE


@pytest.mark.anyio
async def test_start_skips_a_playlist_without_endlist(converter, fake_ffmpeg, session, lives_dir):
    await add_replay(session, 42)
    playlist = write_playlist(lives_dir, 42)
    playlist.write_text("#EXTM3U\n#EXTINF:4.0,\nindex0.ts\n")

    await converter.start(42)

    assert fake_ffmpeg.calls == []
    assert (await reload(session, 42)).mp4_status is Mp4Status.NONE


@pytest.mark.anyio
async def test_start_during_a_conversion_runs_one_ffmpeg(
    converter, fake_ffmpeg, session, lives_dir
):
    await add_replay(session, 42)
    write_playlist(lives_dir, 42)

    await converter.start(42)
    await converter.start(42)
    await wait_conversions(converter)

    assert len(fake_ffmpeg.calls) == 1


@pytest.mark.anyio
async def test_download_during_a_conversion_returns_202_without_second_ffmpeg(
    client, converter, fake_ffmpeg, session, lives_dir
):
    await add_replay(session, 42)
    write_playlist(lives_dir, 42)
    fake_ffmpeg.hang = True
    # ffmpeg bloqué : le délai de 0,05 s du fixture le tuerait avant la suite du test.
    converter.timeout_s = 60
    await converter.start(42)

    response = await client.get("/replays/42/download")

    assert response.status_code == 202
    assert len(fake_ffmpeg.calls) == 1
    await converter.stop()


@pytest.mark.anyio
async def test_stop_kills_ffmpeg_and_leaves_the_row_processing(
    converter, fake_ffmpeg, session, lives_dir, tmp_path
):
    await add_replay(session, 42)
    write_playlist(lives_dir, 42)
    fake_ffmpeg.hang = True
    # ffmpeg bloqué : le délai de 0,05 s du fixture le tuerait avant la suite du test.
    converter.timeout_s = 60
    await converter.start(42)
    while not fake_ffmpeg.processes:
        await asyncio.sleep(0)

    await converter.stop()

    assert fake_ffmpeg.processes[0].killed
    assert not (tmp_path / "42.mp4.part").exists()
    assert (await reload(session, 42)).mp4_status is Mp4Status.PROCESSING


@pytest.mark.anyio
async def test_start_unconverted_only_takes_finished_replays_in_none(
    converter, fake_ffmpeg, session, lives_dir
):
    await add_replay(session, 1)
    await add_replay(session, 2, mp4_status=Mp4Status.READY)
    await add_replay(session, 3, ended_at=None, duration_s=None)
    for stream_id in (1, 2, 3):
        write_playlist(lives_dir, stream_id)

    await converter.start_unconverted()
    await wait_conversions(converter)

    assert fake_ffmpeg.calls == [tuple(converter.ffmpeg_args(1))]
