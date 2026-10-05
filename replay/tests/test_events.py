import logging

import pytest

from app.services.live_event_service import on_stream_ended, on_stream_started
from tests.factories import add_replay, make_ended, make_started, reload, write_playlist


def warning_records(caplog):
    return [record for record in caplog.records if record.levelno == logging.WARNING]


@pytest.mark.anyio
async def test_started_alone_creates_a_hidden_row(session):
    await on_stream_started(session, make_started())

    stored_replay = await reload(session, 42)
    assert stored_replay.title == "Speedrun Any%"
    assert stored_replay.ended_at is None


@pytest.mark.anyio
async def test_started_then_ended_gives_a_full_replay(session, lives_dir):
    await on_stream_started(session, make_started())
    await on_stream_ended(session, make_ended(), lives_dir)

    stored_replay = await reload(session, 42)
    assert stored_replay.title == "Speedrun Any%"
    assert stored_replay.game == "Celeste"
    assert stored_replay.ended_at is not None
    assert stored_replay.duration_s == 5400.0


@pytest.mark.anyio
async def test_ended_then_started_gives_a_full_replay(session, lives_dir):
    await on_stream_ended(session, make_ended(), lives_dir)
    await on_stream_started(session, make_started())

    stored_replay = await reload(session, 42)
    assert stored_replay.streamer_name == "Célèste"
    assert stored_replay.ended_at is not None
    assert stored_replay.duration_s == 5400.0


@pytest.mark.anyio
async def test_ended_twice_keeps_the_first_end(session, lives_dir):
    await on_stream_ended(session, make_ended(duration_s=5400.0), lives_dir)
    await on_stream_ended(session, make_ended(duration_s=1.0), lives_dir)

    stored_replay = await reload(session, 42)
    assert stored_replay.duration_s == 5400.0


@pytest.mark.anyio
async def test_normal_end_does_not_check_the_playlist(session, lives_dir):
    # Aucune playlist dans LIVES_DIR : seul un live terminé en erreur la vérifie.
    await on_stream_ended(session, make_ended(), lives_dir)

    assert (await reload(session, 42)).ended_at is not None


@pytest.mark.anyio
async def test_error_end_with_playlist_creates_the_replay(session, lives_dir):
    write_playlist(lives_dir, 42)

    await on_stream_ended(session, make_ended(reason="error"), lives_dir)

    assert (await reload(session, 42)).ended_at is not None


@pytest.mark.anyio
async def test_error_end_without_playlist_removes_the_row(session, lives_dir):
    await on_stream_started(session, make_started())

    await on_stream_ended(session, make_ended(reason="error"), lives_dir)

    assert await reload(session, 42) is None


@pytest.mark.anyio
async def test_error_end_without_lives_dir_keeps_the_replay(session, tmp_path, caplog):
    # LIVES_DIR mal configuré ou volume non monté : rien ne prouve que la playlist manque.
    await on_stream_ended(session, make_ended(reason="error"), tmp_path / "not-mounted")

    assert (await reload(session, 42)).ended_at is not None
    assert len(warning_records(caplog)) == 1


@pytest.mark.anyio
async def test_error_end_with_unreadable_playlist_keeps_the_replay(session, lives_dir, caplog):
    # Un fichier à la place du dossier du live : erreur disque autre que « fichier absent ».
    (lives_dir / "42").write_text("")

    await on_stream_ended(session, make_ended(reason="error"), lives_dir)

    assert (await reload(session, 42)).ended_at is not None
    assert len(warning_records(caplog)) == 1


@pytest.mark.anyio
async def test_existing_replay_is_not_touched_by_a_late_error_end(session, lives_dir):
    await add_replay(session, 42)

    await on_stream_ended(session, make_ended(reason="error"), lives_dir)

    assert await reload(session, 42) is not None
