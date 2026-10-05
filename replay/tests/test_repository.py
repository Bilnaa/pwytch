import pytest

from app.models import Mp4Status
from app.repositories.replay_repository import (
    claim_conversion,
    finish_conversion,
    reset_conversion,
    reset_processing,
)
from tests.factories import add_replay, reload


@pytest.mark.anyio
async def test_first_claim_wins_and_marks_processing(session):
    await add_replay(session, 42)

    assert await claim_conversion(session, 42) is True
    assert (await reload(session, 42)).mp4_status is Mp4Status.PROCESSING


@pytest.mark.anyio
async def test_second_claim_loses(session):
    await add_replay(session, 42)
    await claim_conversion(session, 42)

    assert await claim_conversion(session, 42) is False


@pytest.mark.anyio
@pytest.mark.parametrize("status", [Mp4Status.READY, Mp4Status.FAILED])
async def test_claim_needs_status_none(session, status):
    await add_replay(session, 42, mp4_status=status)

    assert await claim_conversion(session, 42) is False
    assert (await reload(session, 42)).mp4_status is status


@pytest.mark.anyio
async def test_live_in_progress_cannot_be_claimed(session):
    await add_replay(session, 42, ended_at=None, duration_s=None)

    assert await claim_conversion(session, 42) is False


@pytest.mark.anyio
async def test_unknown_replay_cannot_be_claimed(session):
    assert await claim_conversion(session, 42) is False


@pytest.mark.anyio
@pytest.mark.parametrize("status", [Mp4Status.READY, Mp4Status.FAILED])
async def test_reset_conversion_puts_back_the_expected_status_to_none(session, status):
    await add_replay(session, 42, mp4_status=status)

    assert await reset_conversion(session, 42, status) is True
    assert (await reload(session, 42)).mp4_status is Mp4Status.NONE


@pytest.mark.anyio
async def test_reset_conversion_keeps_a_status_changed_meanwhile(session):
    # Une autre requête a déjà remis à none et relancé ffmpeg : on n'écrase pas processing.
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)

    assert await reset_conversion(session, 42, Mp4Status.FAILED) is False
    assert (await reload(session, 42)).mp4_status is Mp4Status.PROCESSING


@pytest.mark.anyio
async def test_reset_processing_only_touches_processing(session):
    await add_replay(session, 1, mp4_status=Mp4Status.PROCESSING)
    await add_replay(session, 2, mp4_status=Mp4Status.READY)

    assert await reset_processing(session) == 1
    assert (await reload(session, 1)).mp4_status is Mp4Status.NONE
    assert (await reload(session, 2)).mp4_status is Mp4Status.READY


@pytest.mark.anyio
async def test_finish_conversion_writes_the_result_of_a_processing_replay(session):
    await add_replay(session, 42, mp4_status=Mp4Status.PROCESSING)

    assert await finish_conversion(session, 42, Mp4Status.READY) is True
    assert (await reload(session, 42)).mp4_status is Mp4Status.READY


@pytest.mark.anyio
async def test_finish_conversion_does_not_overwrite_a_reset_status(session):
    # Ligne remise à none entre-temps : un ffmpeg qui finit en retard n'écrase rien.
    await add_replay(session, 42, mp4_status=Mp4Status.NONE)

    assert await finish_conversion(session, 42, Mp4Status.READY) is False
    assert (await reload(session, 42)).mp4_status is Mp4Status.NONE
