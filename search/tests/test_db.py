from datetime import UTC, datetime

import pytest
from app.infra.config import Settings
from app.infra.models import Stream, Streamer
from sqlalchemy import inspect


@pytest.mark.anyio
async def test_init_db_creates_tables(engine):
    async with engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )

    assert {"streamers", "streams"} <= set(table_names)


@pytest.mark.anyio
async def test_streamer_round_trip(session):
    session.add(
        Streamer(streamer_id="42", streamer_name="Célèste", search_text="celeste")
    )
    await session.commit()
    session.expunge_all()

    stored_streamer = await session.get(Streamer, "42")

    assert stored_streamer is not None
    assert stored_streamer.streamer_name == "Célèste"
    assert stored_streamer.search_text == "celeste"


@pytest.mark.anyio
async def test_stream_accepts_ended_before_started(session):
    ended_at = datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
    session.add(Stream(stream_id="s1", streamer_id="42", ended_at=ended_at))
    await session.commit()
    session.expunge_all()

    stored_stream = await session.get(Stream, "s1")

    assert stored_stream is not None
    assert stored_stream.title is None
    assert stored_stream.game is None
    assert stored_stream.started_at is None
    # SQLite perd le fuseau à la relecture ; Postgres (timestamptz) le garde.
    assert stored_stream.ended_at.replace(tzinfo=UTC) == ended_at


def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:secret@db/search")

    assert Settings().database_url == "postgresql+asyncpg://user:secret@db/search"
