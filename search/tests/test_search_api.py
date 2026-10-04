import logging

import pytest
from common.events import ItemType
from common.mqtt import NotConnectedError

from app.indexer import on_stream_ended, on_stream_started
from app.infra.db import get_session
from app.main import app
from tests.factories import (
    FIRST_START,
    SECOND_START,
    make_ended,
    make_started,
    published_hits,
)

SEARCH_URL = "/search/streamers"


async def start_live(session, streamer_number: int, **overrides) -> None:
    # Ids propres à chaque streamer, titre et jeu vides : les valeurs par défaut
    # des fabriques ne correspondent jamais à une requête.
    event_fields = {
        "streamer_id": streamer_number,
        "stream_id": streamer_number,
        "streamer_name": f"Streamer {streamer_number}",
        "title": "",
        "game": "",
    }
    await on_stream_started(session, make_started(**(event_fields | overrides)))


async def end_live(session, streamer_number: int, **overrides) -> None:
    event_fields = {
        "streamer_id": streamer_number,
        "stream_id": streamer_number,
    }
    await on_stream_ended(session, make_ended(**(event_fields | overrides)))


async def search(client, **params):
    response = await client.get(SEARCH_URL, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def matching_names(client, search_query: str) -> list[str]:
    body = await search(client, q=search_query)
    return [item["streamer_name"] for item in body["items"]]


# Validation


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "   "},
        {"q": "a"},
        {"q": " a "},
        {"q": "x" * 101},
        {"q": "ab", "size": 0},
        {"q": "ab", "size": 51},
        {"q": "ab", "page": 0},
        # Deux diacritiques combinants : 2 caractères, mais vide après normalize().
        {"q": "\u0301\u0301"},
        {"q": "\u0301 \u0301"},
        {"q": "a\x00"},
    ],
    ids=[
        "missing",
        "empty",
        "spaces-only",
        "one-char",
        "one-char-after-strip",
        "too-long",
        "size-zero",
        "size-too-big",
        "page-zero",
        "combining-marks-only",
        "combining-marks-around-space",
        "null-character",
    ],
)
async def test_invalid_parameters_return_422(client, params):
    response = await client.get(SEARCH_URL, params=params)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_query_of_100_characters_is_accepted(client):
    response = await client.get(SEARCH_URL, params={"q": "x" * 100})

    assert response.status_code == 200


# Correspondance


@pytest.mark.anyio
async def test_no_match_returns_empty_page(client, session):
    await start_live(session, 1, streamer_name="Alice")

    body = await search(client, q="zzz")

    assert body == {"items": [], "total": 0, "page": 1, "size": 20}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "event_fields, search_query",
    [
        ({"streamer_name": "Celeste"}, "cel"),
        ({"game": "Hollow Knight"}, "hollow"),
        ({"title": "Speedrun any%"}, "speedrun"),
        ({"streamer_name": "Célèste"}, "celeste"),
        ({"streamer_name": "Celeste"}, "Célè"),
    ],
    ids=["name", "game", "title", "accent-in-data", "accent-in-query"],
)
async def test_query_matches_one_streamer(client, session, event_fields, search_query):
    await start_live(session, 1, **event_fields)
    await start_live(session, 2, streamer_name="Other")

    body = await search(client, q=search_query)

    assert body["total"] == 1
    assert [item["streamer_id"] for item in body["items"]] == [1]


@pytest.mark.anyio
async def test_query_is_stripped_before_matching(client, session):
    await start_live(session, 1, streamer_name="Celeste")

    assert await matching_names(client, "  cel  ") == ["Celeste"]


@pytest.mark.anyio
async def test_underscore_is_matched_literally(client, session):
    await start_live(session, 1, streamer_name="a_b")
    await start_live(session, 2, streamer_name="axb")

    assert await matching_names(client, "a_b") == ["a_b"]


@pytest.mark.anyio
async def test_percent_is_matched_literally(client, session):
    await start_live(session, 1, streamer_name="First", title="100% run")
    await start_live(session, 2, streamer_name="Second", title="100 run")

    assert await matching_names(client, "100%") == ["First"]


# Contenu des résultats et statut live


@pytest.mark.anyio
async def test_live_result_contains_every_field(client, session):
    await start_live(
        session, 1, streamer_name="Celeste", title="Speedrun any%", game="Celeste"
    )

    body = await search(client, q="cel")

    assert body["items"] == [
        {
            "streamer_id": 1,
            "streamer_name": "Celeste",
            "last_title": "Speedrun any%",
            "last_game": "Celeste",
            "is_live": True,
            "live_stream_id": 1,
        }
    ]


@pytest.mark.anyio
async def test_ended_live_is_not_live(client, session):
    await start_live(session, 1, streamer_name="Celeste", title="Speedrun")
    await end_live(session, 1)

    [result] = (await search(client, q="cel"))["items"]

    assert result["is_live"] is False
    assert result["live_stream_id"] is None
    assert result["last_title"] == "Speedrun"


@pytest.mark.anyio
async def test_ended_before_started_is_not_live(client, session):
    await end_live(session, 1)
    await start_live(session, 1, streamer_name="Celeste")

    [result] = (await search(client, q="cel"))["items"]

    assert result["is_live"] is False
    assert result["live_stream_id"] is None


@pytest.mark.anyio
async def test_two_open_lives_report_the_latest(client, session):
    await start_live(
        session, 1, stream_id=1, streamer_name="Celeste", started_at=FIRST_START
    )
    await start_live(
        session, 1, stream_id=2, streamer_name="Celeste", started_at=SECOND_START
    )

    [result] = (await search(client, q="cel"))["items"]

    assert result["is_live"] is True
    assert result["live_stream_id"] == 2


# Tri et pagination


@pytest.mark.anyio
async def test_live_streamers_come_first_then_by_name(client, session):
    # Même casse partout : l'ordre des noms ne dépend pas de la collation.
    await start_live(session, 1, streamer_name="Carl", title="xx")
    await end_live(session, 1)
    await start_live(session, 2, streamer_name="Bob", title="xx")
    await start_live(session, 3, streamer_name="Alice", title="xx")
    await end_live(session, 3)

    assert await matching_names(client, "xx") == ["Bob", "Alice", "Carl"]


@pytest.mark.anyio
async def test_name_order_ignores_case(client, session):
    await start_live(session, 1, streamer_name="carl", title="xx")
    await start_live(session, 2, streamer_name="Bob", title="xx")
    await start_live(session, 3, streamer_name="alice", title="xx")

    assert await matching_names(client, "xx") == ["alice", "Bob", "carl"]


@pytest.mark.anyio
async def test_same_start_time_result_matches_indexed_stream(client, session):
    # Même départage que l'indexeur : last_title doit être ce que search_text indexe.
    await start_live(session, 1, stream_id=1, streamer_name="Celeste", title="Alpha")
    await start_live(session, 1, stream_id=2, streamer_name="Celeste", title="Beta")

    [result] = (await search(client, q="beta"))["items"]

    assert result["last_title"] == "Beta"
    assert result["live_stream_id"] == 2


async def start_25_streamers(session) -> None:
    # Noms avec zéros devant : ordre texte = ordre numérique ("Match 02" < "Match 10").
    for streamer_number in range(1, 26):
        await start_live(
            session, streamer_number, streamer_name=f"Match {streamer_number:02d}"
        )


@pytest.mark.anyio
async def test_default_page_size_is_20(client, session):
    await start_25_streamers(session)

    body = await search(client, q="match")

    assert len(body["items"]) == 20
    assert body["total"] == 25
    assert body["page"] == 1
    assert body["size"] == 20
    assert body["items"][0]["streamer_name"] == "Match 01"


@pytest.mark.anyio
async def test_second_page_holds_the_rest(client, session):
    await start_25_streamers(session)

    body = await search(client, q="match", page=2, size=20)

    names = [item["streamer_name"] for item in body["items"]]
    assert names == ["Match 21", "Match 22", "Match 23", "Match 24", "Match 25"]
    assert body["total"] == 25


@pytest.mark.anyio
async def test_page_past_the_end_is_empty_with_real_total(client, session):
    await start_25_streamers(session)

    body = await search(client, q="match", page=5)

    assert body["items"] == []
    assert body["total"] == 25


# Publication de search/hit


async def start_zera_streamers(session, count: int) -> None:
    for streamer_number in range(1, count + 1):
        await start_live(
            session, streamer_number, streamer_name=f"Zera {streamer_number}"
        )


@pytest.mark.anyio
async def test_each_streamer_found_is_published(client, session, fake_mqtt):
    await start_zera_streamers(session, 2)

    body = await search(client, q="zera")

    hits = published_hits(fake_mqtt)
    assert len(body["items"]) == 2
    assert [hit.item_id for hit in hits] == [
        str(item["streamer_id"]) for item in body["items"]
    ]
    assert [hit.item_type for hit in hits] == [ItemType.STREAMER, ItemType.STREAMER]
    assert [hit.query for hit in hits] == ["zera", "zera"]
    assert hits[0].hit_at.tzinfo is not None
    assert len({hit.hit_at for hit in hits}) == 1


@pytest.mark.anyio
async def test_published_query_is_stripped(client, session, fake_mqtt):
    await start_zera_streamers(session, 1)

    await search(client, q="  zera ")

    [hit] = published_hits(fake_mqtt)
    assert hit.query == "zera"


@pytest.mark.anyio
async def test_only_the_current_page_is_published(client, session, fake_mqtt):
    await start_zera_streamers(session, 3)

    body = await search(client, q="zera", page=2, size=2)

    # Sans ce contrôle, une page vide donnerait [] == [] et le test passerait.
    assert len(body["items"]) == 1
    assert [hit.item_id for hit in published_hits(fake_mqtt)] == [
        str(item["streamer_id"]) for item in body["items"]
    ]


@pytest.mark.anyio
async def test_page_past_the_end_publishes_nothing(client, session, fake_mqtt):
    # Même branche que « aucun résultat », mais avec un total > 0.
    await start_zera_streamers(session, 3)

    body = await search(client, q="zera", page=5, size=2)

    assert body["total"] == 3
    assert published_hits(fake_mqtt) == []


@pytest.mark.anyio
async def test_no_result_publishes_nothing(client, fake_mqtt):
    await search(client, q="zera")

    assert published_hits(fake_mqtt) == []


@pytest.mark.anyio
async def test_invalid_query_publishes_nothing(client, fake_mqtt):
    response = await client.get(SEARCH_URL, params={"q": "a"})

    assert response.status_code == 422
    assert published_hits(fake_mqtt) == []


@pytest.mark.anyio
async def test_broker_down_still_returns_the_results(
    client, session, fake_mqtt, caplog
):
    await start_zera_streamers(session, 1)
    fake_mqtt.publish.side_effect = NotConnectedError("down")

    body = await search(client, q="zera")

    assert [item["streamer_name"] for item in body["items"]] == ["Zera 1"]
    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert [error.getMessage() for error in errors] == [
        "1 search/hit events not published: down"
    ]


@pytest.mark.anyio
async def test_session_is_closed_before_publishing(client, session, fake_mqtt):
    await start_zera_streamers(session, 1)
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

    await search(client, q="zera")

    assert closed_when_publishing == [True]
