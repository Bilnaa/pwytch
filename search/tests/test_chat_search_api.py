import logging
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from common.events import ItemType
from common.mqtt import NotConnectedError

from app.indexer import on_chat_message
from app.infra.db import get_session
from app.main import app
from tests.factories import FIRST_START, make_chat_message, published_hits

STREAM_ID = 1


def chat_search_url(stream_id=STREAM_ID) -> str:
    return f"/search/streams/{stream_id}/messages"


async def post_message(session, rank: int, content: str, **overrides) -> UUID:
    # Un message_id et un sent_at propres à chaque message : le rang fixe l'ordre.
    message_fields = {
        "message_id": uuid4(),
        "stream_id": STREAM_ID,
        "content": content,
        "sent_at": FIRST_START + timedelta(seconds=rank),
    }
    chat_message = make_chat_message(**(message_fields | overrides))
    await on_chat_message(session, chat_message)
    return chat_message.message_id


async def search_chat(client, stream_id=STREAM_ID, **params):
    response = await client.get(chat_search_url(stream_id), params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def matching_ids(client, search_query: str, stream_id=STREAM_ID) -> list[str]:
    body = await search_chat(client, stream_id, q=search_query)
    return [item["message_id"] for item in body]


# Validation


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "   "},
        {"q": "x" * 101},
        # Diacritique combinant seul : 1 caractère, mais vide après normalize().
        {"q": "\u0301"},
        {"q": "\u0301 \u0301"},
        {"q": "\x00"},
    ],
    ids=[
        "missing",
        "empty",
        "spaces-only",
        "too-long",
        "combining-mark-only",
        "combining-marks-around-space",
        "null-character",
    ],
)
async def test_invalid_query_returns_422(client, params):
    response = await client.get(chat_search_url(), params=params)

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    "stream_id",
    ["abc", "0", "2147483648"],
    ids=["not-a-number", "zero", "above-int32"],
)
async def test_invalid_stream_id_returns_422(client, stream_id):
    response = await client.get(chat_search_url(stream_id), params={"q": "gg"})

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    "content, search_query",
    [("gg", "g"), ("ça brûle 🔥", "🔥")],
    ids=["one-letter", "emoji"],
)
async def test_one_character_query_is_accepted(client, session, content, search_query):
    message_id = await post_message(session, 1, content)

    assert await matching_ids(client, search_query) == [str(message_id)]


@pytest.mark.anyio
async def test_query_of_100_characters_is_accepted(client):
    response = await client.get(chat_search_url(), params={"q": "x" * 100})

    assert response.status_code == 200


# Correspondance


@pytest.mark.anyio
async def test_no_match_returns_empty_list(client, session):
    await post_message(session, 1, "GG WP !")

    assert await search_chat(client, q="zzz") == []


@pytest.mark.anyio
async def test_unknown_stream_returns_empty_list(client, session):
    await post_message(session, 1, "GG WP !")

    assert await search_chat(client, stream_id=999, q="gg") == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "content, search_query",
    [
        # SQLite ignore déjà la casse ASCII : seules les majuscules accentuées
        # prouvent que q passe par normalize().
        ("Célèste", "CÉLÈSTE"),
        ("Célèste", "celeste"),
        ("celeste", "célèste"),
        ("ggwp", "gg"),
    ],
    ids=["accented-uppercase-query", "accent-in-data", "accent-in-query", "substring"],
)
async def test_query_matches_message(client, session, content, search_query):
    message_id = await post_message(session, 1, content)

    assert await matching_ids(client, search_query) == [str(message_id)]


@pytest.mark.anyio
async def test_message_of_another_stream_is_not_returned(client, session):
    message_id = await post_message(session, 1, "GG WP !")
    await post_message(session, 2, "GG WP !", stream_id=2)

    assert await matching_ids(client, "gg") == [str(message_id)]


@pytest.mark.anyio
async def test_returns_ten_most_recent_messages(client, session):
    message_ids = [await post_message(session, rank, "gg") for rank in range(12)]

    expected_ids = [str(message_id) for message_id in reversed(message_ids)][:10]
    assert await matching_ids(client, "gg") == expected_ids


@pytest.mark.anyio
async def test_same_sent_at_is_ordered_by_message_id_desc(client, session):
    lower_id = UUID("00000000-0000-4000-8000-000000000001")
    higher_id = UUID("ffffffff-ffff-4fff-bfff-ffffffffffff")
    await post_message(session, 1, "gg", message_id=lower_id)
    await post_message(session, 1, "gg", message_id=higher_id)

    assert await matching_ids(client, "gg") == [str(higher_id), str(lower_id)]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "content, search_query",
    [("1000", "100%"), ("axb", "a_b")],
    ids=["percent", "underscore"],
)
async def test_like_wildcards_are_searched_literally(
    client, session, content, search_query
):
    await post_message(session, 1, content)

    assert await search_chat(client, q=search_query) == []


# Format


@pytest.mark.anyio
async def test_result_has_exact_fields_and_original_content(client, session):
    message_id = await post_message(session, 1, "GG WP !")

    [result] = await search_chat(client, q="gg")

    assert set(result) == {
        "message_id",
        "stream_id",
        "author_name",
        "content",
        "sent_at",
    }
    assert result["message_id"] == str(message_id)
    assert result["stream_id"] == STREAM_ID
    assert result["author_name"] == "Célèste"
    assert result["content"] == "GG WP !"


# Publication de search/hit


@pytest.mark.anyio
async def test_each_message_found_is_published(client, session, fake_mqtt):
    await post_message(session, 1, "gg")
    await post_message(session, 2, "gg wp")

    body = await search_chat(client, q="gg")

    hits = published_hits(fake_mqtt)
    assert len(body) == 2
    assert [hit.item_id for hit in hits] == [item["message_id"] for item in body]
    assert [hit.item_type for hit in hits] == [ItemType.MESSAGE, ItemType.MESSAGE]
    assert [hit.query for hit in hits] == ["gg", "gg"]
    assert hits[0].hit_at.tzinfo is not None
    assert len({hit.hit_at for hit in hits}) == 1


@pytest.mark.anyio
async def test_at_most_10_messages_are_published(client, session, fake_mqtt):
    for rank in range(12):
        await post_message(session, rank, "gg")

    await search_chat(client, q="gg")

    assert len(published_hits(fake_mqtt)) == 10


@pytest.mark.anyio
async def test_message_of_another_live_is_not_published(client, session, fake_mqtt):
    await post_message(session, 1, "gg", stream_id=2)

    assert await search_chat(client, q="gg") == []
    assert published_hits(fake_mqtt) == []


@pytest.mark.anyio
async def test_no_matching_message_publishes_nothing(client, session, fake_mqtt):
    await post_message(session, 1, "salut")

    assert await search_chat(client, q="gg") == []
    assert published_hits(fake_mqtt) == []


@pytest.mark.anyio
async def test_invalid_chat_query_publishes_nothing(client, session, fake_mqtt):
    await post_message(session, 1, "gg")

    response = await client.get(chat_search_url(), params={"q": ""})

    assert response.status_code == 422
    assert published_hits(fake_mqtt) == []


@pytest.mark.anyio
async def test_broker_down_still_returns_the_messages(
    client, session, fake_mqtt, caplog
):
    message_id = await post_message(session, 1, "gg")
    fake_mqtt.publish.side_effect = NotConnectedError("down")

    body = await search_chat(client, q="gg")

    assert [item["message_id"] for item in body] == [str(message_id)]
    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert [error.getMessage() for error in errors] == [
        "1 search/hit events not published: down"
    ]


@pytest.mark.anyio
async def test_chat_session_is_closed_before_publishing(client, session, fake_mqtt):
    await post_message(session, 1, "gg")
    session_state = {"closed": False}
    closed_when_publishing = []

    async def tracked_get_session():
        yield session
        session_state["closed"] = True

    # Remplace l'override de la fixture client, vidé à la fin du test.
    app.dependency_overrides[get_session] = tracked_get_session
    fake_mqtt.publish.side_effect = lambda topic, event: closed_when_publishing.append(
        session_state["closed"]
    )

    await search_chat(client, q="gg")

    assert closed_when_publishing == [True]
