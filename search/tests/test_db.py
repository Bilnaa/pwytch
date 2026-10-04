from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import inspect

from app.infra.config import Settings
from app.infra.models import IndexedChatMessage, Stream, Streamer
from tests.factories import FIRST_START, as_utc, reload

MESSAGE_ID = UUID("3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97")


async def inspect_database(engine, read_metadata):
    async with engine.connect() as connection:
        return await connection.run_sync(
            lambda sync_connection: read_metadata(inspect(sync_connection))
        )


@pytest.mark.anyio
async def test_init_db_creates_tables(engine):
    table_names = await inspect_database(
        engine, lambda inspector: inspector.get_table_names()
    )

    assert {"streamers", "streams", "chat_messages"} <= set(table_names)


@pytest.mark.anyio
async def test_streamer_round_trip(session):
    session.add(
        Streamer(streamer_id=42, streamer_name="Célèste", search_text="celeste")
    )
    await session.commit()
    session.expunge_all()

    stored_streamer = await session.get(Streamer, 42)

    assert stored_streamer is not None
    assert stored_streamer.streamer_name == "Célèste"
    assert stored_streamer.search_text == "celeste"


@pytest.mark.anyio
async def test_stream_accepts_ended_before_started(session):
    ended_at = datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
    session.add(Stream(stream_id=1, streamer_id=42, ended_at=ended_at))
    await session.commit()
    session.expunge_all()

    stored_stream = await session.get(Stream, 1)

    assert stored_stream is not None
    assert stored_stream.title is None
    assert stored_stream.game is None
    assert stored_stream.started_at is None
    # SQLite perd le fuseau à la relecture ; Postgres (timestamptz) le garde.
    assert stored_stream.ended_at.replace(tzinfo=UTC) == ended_at


@pytest.mark.anyio
async def test_chat_messages_has_index_on_stream_sent_at_message_id(engine):
    indexes = await inspect_database(
        engine, lambda inspector: inspector.get_indexes("chat_messages")
    )

    assert ["stream_id", "sent_at", "message_id"] in [
        index["column_names"] for index in indexes
    ]


@pytest.mark.anyio
async def test_chat_messages_has_index_on_sent_at_message_id(engine):
    indexes = await inspect_database(
        engine, lambda inspector: inspector.get_indexes("chat_messages")
    )

    assert ["sent_at", "message_id"] in [index["column_names"] for index in indexes]


@pytest.mark.anyio
async def test_chat_message_round_trip(session):
    session.add(
        IndexedChatMessage(
            message_id=MESSAGE_ID,
            stream_id=7,
            author_id=3,
            author_name="Célèste",
            content="GG WP !",
            search_text="gg wp !",
            sent_at=FIRST_START,
        )
    )
    await session.commit()

    stored_message = await reload(session, IndexedChatMessage, MESSAGE_ID)

    assert stored_message is not None
    # Relu comme un UUID, pas comme le texte stocké par SQLite.
    assert stored_message.message_id == MESSAGE_ID
    assert stored_message.stream_id == 7
    assert stored_message.author_id == 3
    assert stored_message.author_name == "Célèste"
    assert stored_message.content == "GG WP !"
    assert stored_message.search_text == "gg wp !"
    assert as_utc(stored_message.sent_at) == FIRST_START


def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:secret@db/search")

    assert Settings().database_url == "postgresql+asyncpg://user:secret@db/search"
