import logging

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import db
from app.core.db import try_init_db
from app.models import Mp4Status, Replay
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


@pytest.mark.parametrize("column_name", ["started_at", "ended_at"])
def test_datetimes_keep_their_time_zone(column_name):
    # SQLite ne montre pas la différence : sans timezone=True, Postgres refuserait les events.
    assert Replay.__table__.c[column_name].type.timezone is True


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


@pytest.mark.anyio
async def test_row_inserted_without_orm_gets_status_none(session):
    await session.execute(text("INSERT INTO replays (stream_id, streamer_id) VALUES (44, 7)"))
    await session.commit()

    assert (await reload(session, 44)).mp4_status is Mp4Status.NONE


@pytest.mark.anyio
async def test_unknown_status_is_refused_by_the_database(session):
    with pytest.raises(IntegrityError):
        await session.execute(
            text("INSERT INTO replays (stream_id, streamer_id, mp4_status) VALUES (45, 7, 'done')")
        )


# Démarrage sans base


@pytest.mark.anyio
async def test_try_init_db_creates_the_tables_when_the_database_is_up(engine):
    assert await try_init_db(engine) is True


@pytest.mark.anyio
async def test_try_init_db_logs_a_warning_when_the_database_is_down(tmp_path, caplog):
    # Dossier inexistant : SQLite ne peut pas ouvrir le fichier, comme une base injoignable.
    unreachable_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/missing/replay.db")

    assert await try_init_db(unreachable_engine) is False

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    await unreachable_engine.dispose()


@pytest.mark.anyio
async def test_try_init_db_catches_a_refused_connection(engine, monkeypatch, caplog):
    # asyncpg lève un ConnectionRefusedError brut (un OSError), pas une erreur SQLAlchemy.
    async def refuse_connection(_engine):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(db, "init_db", refuse_connection)

    assert await try_init_db(engine) is False
    assert "connection refused" in caplog.text
