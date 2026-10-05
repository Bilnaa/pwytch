import asyncio
import logging

import pytest

from app.models import Mp4Status
from app.services.conversion_service import Mp4Converter
from tests.factories import add_replay, reload


def error_records(caplog):
    return [record for record in caplog.records if record.levelno == logging.ERROR]


def broken_session_factory():
    # Comme asyncpg quand Postgres est coupé : un OSError brut.
    raise ConnectionRefusedError("db down")


@pytest.mark.anyio
async def test_ffmpeg_reads_the_playlist_in_the_lives_dir_and_copies_the_streams(
    converter, lives_dir, tmp_path
):
    assert converter.ffmpeg_args(42) == [
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
        "-i", str(lives_dir / "42" / "index.m3u8"),
        "-c", "copy", "-f", "mp4", str(tmp_path / "42.mp4.part"),
    ]  # fmt: skip


@pytest.mark.anyio
async def test_success_renames_the_part_file_and_marks_ready(
    converter, fake_ffmpeg, session, tmp_path
):
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)

    await converter.convert(42)

    assert fake_ffmpeg.calls == [tuple(converter.ffmpeg_args(42))]
    assert (tmp_path / "42.mp4").read_bytes() == b"partial mp4"
    assert not (tmp_path / "42.mp4.part").exists()
    assert (await reload(session, 42)).mp4_status is Mp4Status.READY


@pytest.mark.anyio
async def test_failure_logs_stderr_removes_the_part_file_and_marks_failed(
    converter, fake_ffmpeg, session, tmp_path, caplog
):
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)
    fake_ffmpeg.returncode = 1
    fake_ffmpeg.stderr = b"index.m3u8: No such file or directory"

    await converter.convert(42)

    assert not (tmp_path / "42.mp4.part").exists()
    assert not (tmp_path / "42.mp4").exists()
    assert (await reload(session, 42)).mp4_status is Mp4Status.FAILED
    [error] = error_records(caplog)
    assert "No such file or directory" in error.getMessage()


@pytest.mark.anyio
async def test_timeout_kills_ffmpeg_and_marks_failed(
    converter, fake_ffmpeg, session, tmp_path, caplog
):
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)
    fake_ffmpeg.hang = True

    await converter.convert(42)

    assert fake_ffmpeg.processes[0].killed
    assert not (tmp_path / "42.mp4.part").exists()
    assert (await reload(session, 42)).mp4_status is Mp4Status.FAILED
    assert len(error_records(caplog)) == 1


@pytest.mark.anyio
async def test_missing_ffmpeg_marks_failed(converter, fake_ffmpeg, session, caplog):
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)
    fake_ffmpeg.missing = True

    await converter.convert(42)

    assert (await reload(session, 42)).mp4_status is Mp4Status.FAILED
    assert len(error_records(caplog)) == 1


@pytest.mark.anyio
async def test_convert_never_raises(fake_ffmpeg, tmp_path, caplog):
    broken_converter = Mp4Converter(
        broken_session_factory, tmp_path / "lives", tmp_path, 1
    )

    await broken_converter.convert(42)

    [error] = error_records(caplog)
    assert error.exc_info is not None


@pytest.mark.anyio
async def test_reset_interrupted_resets_processing_and_removes_part_files(
    converter, session, tmp_path
):
    await add_replay(session, 1, mp4_status=Mp4Status.PROCESSING)
    (tmp_path / "1.mp4.part").write_bytes(b"partial mp4")
    (tmp_path / "2.mp4").write_bytes(b"mp4")

    await converter.reset_interrupted()

    assert (await reload(session, 1)).mp4_status is Mp4Status.NONE
    assert not (tmp_path / "1.mp4.part").exists()
    assert (tmp_path / "2.mp4").exists()


@pytest.mark.anyio
async def test_reset_interrupted_creates_the_replays_dir(session_factory, tmp_path):
    replays_dir = tmp_path / "replays"

    await Mp4Converter(
        session_factory, tmp_path / "lives", replays_dir, 1
    ).reset_interrupted()

    assert replays_dir.is_dir()


@pytest.mark.anyio
async def test_reset_interrupted_with_database_down_does_not_stop_the_start(
    tmp_path, caplog
):
    # Même règle que try_init_db : une base coupée n'empêche pas le service de démarrer.
    broken_converter = Mp4Converter(
        broken_session_factory, tmp_path / "lives", tmp_path, 1
    )
    (tmp_path / "1.mp4.part").write_bytes(b"partial mp4")

    await broken_converter.reset_interrupted()

    assert not (tmp_path / "1.mp4.part").exists()
    warnings = [
        record for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert len(warnings) == 1


@pytest.mark.anyio
async def test_late_finish_keeps_the_status_set_meanwhile(
    converter, fake_ffmpeg, session, caplog
):
    await add_replay(session, 42, mp4_status=Mp4Status.NONE)

    await converter.convert(42)

    assert (await reload(session, 42)).mp4_status is Mp4Status.NONE
    warnings = [
        record for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert len(warnings) == 1


@pytest.mark.anyio
async def test_cancelled_conversion_kills_ffmpeg_and_removes_the_part_file(
    session_factory, fake_ffmpeg, session, tmp_path
):
    # Annulation à l'arrêt du service : ffmpeg ne doit pas rester orphelin.
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)
    slow_converter = Mp4Converter(
        session_factory, tmp_path / "lives", tmp_path, timeout_s=60
    )
    fake_ffmpeg.hang = True

    conversion_task = asyncio.create_task(slow_converter.convert(42))
    while not fake_ffmpeg.processes:
        await asyncio.sleep(0)
    conversion_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await conversion_task
    assert fake_ffmpeg.processes[0].killed
    assert not (tmp_path / "42.mp4.part").exists()
