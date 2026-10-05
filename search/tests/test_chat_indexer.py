import logging

import pytest

from app.models import IndexedChatMessage
from app.services.indexing_service import on_chat_message, on_stream_ended
from tests.factories import (
    MESSAGE_ID,
    count_rows,
    make_chat_message,
    make_ended,
    reload,
)


def warning_records(caplog):
    return [record for record in caplog.records if record.levelno == logging.WARNING]


@pytest.mark.anyio
async def test_first_message_is_indexed(session):
    await on_chat_message(session, make_chat_message())

    assert await count_rows(session, IndexedChatMessage) == 1
    message = await reload(session, IndexedChatMessage, MESSAGE_ID)
    assert message.content == "GG WP !"
    assert message.search_text == "gg wp !"
    assert message.author_id == 1


@pytest.mark.anyio
async def test_same_event_twice_is_stored_once_without_warning(session, caplog):
    chat_message = make_chat_message()

    await on_chat_message(session, chat_message)
    await on_chat_message(session, chat_message)

    assert await count_rows(session, IndexedChatMessage) == 1
    assert warning_records(caplog) == []


@pytest.mark.anyio
async def test_same_message_with_new_event_id_is_stored_once(session, caplog):
    await on_chat_message(session, make_chat_message())
    await on_chat_message(session, make_chat_message())

    assert await count_rows(session, IndexedChatMessage) == 1
    assert warning_records(caplog) == []


@pytest.mark.anyio
async def test_divergent_duplicate_keeps_first_and_logs_warning(session, caplog):
    await on_chat_message(session, make_chat_message(content="a"))
    await on_chat_message(session, make_chat_message(content="b"))

    assert await count_rows(session, IndexedChatMessage) == 1
    message = await reload(session, IndexedChatMessage, MESSAGE_ID)
    assert message.content == "a"
    [warning] = warning_records(caplog)
    assert str(MESSAGE_ID) in warning.getMessage()


@pytest.mark.anyio
async def test_message_for_unknown_stream_is_indexed(session):
    # Aucun stream/started avant : pas de clé étrangère vers streams.
    await on_chat_message(session, make_chat_message(stream_id=42))

    message = await reload(session, IndexedChatMessage, MESSAGE_ID)
    assert message.stream_id == 42


@pytest.mark.anyio
async def test_message_after_stream_ended_is_indexed(session):
    await on_stream_ended(session, make_ended())

    await on_chat_message(session, make_chat_message())

    assert await count_rows(session, IndexedChatMessage) == 1
