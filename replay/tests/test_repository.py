import pytest

from app.infra.models import Mp4Status
from app.infra.repository import claim_conversion, reset_processing, set_mp4_status
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
async def test_set_mp4_status(session):
    await add_replay(session, 42)

    await set_mp4_status(session, 42, Mp4Status.READY)

    assert (await reload(session, 42)).mp4_status is Mp4Status.READY


@pytest.mark.anyio
async def test_reset_processing_only_touches_processing(session):
    await add_replay(session, 1, mp4_status=Mp4Status.PROCESSING)
    await add_replay(session, 2, mp4_status=Mp4Status.READY)

    assert await reset_processing(session) == 1
    assert (await reload(session, 1)).mp4_status is Mp4Status.NONE
    assert (await reload(session, 2)).mp4_status is Mp4Status.READY
