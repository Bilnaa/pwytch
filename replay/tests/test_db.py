import pytest
from sqlalchemy import inspect

from app.infra.models import Mp4Status
from tests.factories import FIRST_END, add_replay, reload


async def inspect_database(engine, read_metadata):
    async with engine.connect() as connection:
        return await connection.run_sync(
            lambda sync_connection: read_metadata(inspect(sync_connection))
        )


@pytest.mark.anyio
async def test_init_db_creates_the_replays_table(engine):
    table_names = await inspect_database(engine, lambda inspector: inspector.get_table_names())

    assert "replays" in table_names


@pytest.mark.anyio
async def test_replays_has_index_on_ended_at_stream_id(engine):
    indexes = await inspect_database(engine, lambda inspector: inspector.get_indexes("replays"))

    assert ["ended_at", "stream_id"] in [index["column_names"] for index in indexes]


@pytest.mark.anyio
async def test_replay_round_trip_with_default_status(session):
    await add_replay(session, 42)

    stored_replay = await reload(session, 42)

    assert stored_replay.streamer_name == "Célèste"
    assert stored_replay.mp4_status is Mp4Status.NONE
    # SQLite perd le fuseau à la relecture ; Postgres (timestamptz) le garde.
    assert stored_replay.ended_at.replace(tzinfo=FIRST_END.tzinfo) == FIRST_END


@pytest.mark.anyio
async def test_live_in_progress_keeps_null_end(session):
    await add_replay(session, 43, ended_at=None, duration_s=None)

    stored_replay = await reload(session, 43)

    assert stored_replay.ended_at is None
    assert stored_replay.duration_s is None
