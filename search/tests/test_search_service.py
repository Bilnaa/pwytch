import pytest
from common.events import ItemType

from app.services import search_service
from app.services.indexing_service import on_chat_message, on_stream_started
from tests.factories import make_chat_message, make_started


class RecordingHitPublisher:
    """Faux HitPublisher : garde les appels au lieu de programmer une tâche de fond."""

    def __init__(self):
        self.calls = []

    def schedule(self, item_type, item_ids, search_query):
        self.calls.append((item_type, list(item_ids), search_query))


@pytest.mark.anyio
async def test_search_streamers_returns_a_page_and_schedules_the_streamer_hits(session):
    await on_stream_started(session, make_started(streamer_id=42, streamer_name="Zerator"))
    hits = RecordingHitPublisher()

    page = await search_service.search_streamers(session, hits, "zera", 1, 20)

    assert [result.streamer_id for result in page.items] == [42]
    assert (page.total, page.page, page.size) == (1, 1, 20)
    assert hits.calls == [(ItemType.STREAMER, [42], "zera")]


@pytest.mark.anyio
async def test_search_without_result_still_hands_an_empty_list_to_the_publisher(session):
    hits = RecordingHitPublisher()

    page = await search_service.search_streamers(session, hits, "zera", 1, 20)

    assert page.items == []
    # HitPublisher.schedule ne programme rien pour une liste vide (testé dans test_hits.py).
    assert hits.calls == [(ItemType.STREAMER, [], "zera")]


@pytest.mark.anyio
async def test_chat_searches_schedule_the_message_hits(session):
    message = make_chat_message(stream_id=1, content="GG WP !")
    await on_chat_message(session, message)
    hits = RecordingHitPublisher()

    in_live = await search_service.search_chat_messages(session, hits, 1, "gg")
    everywhere = await search_service.search_all_chat_messages(session, hits, "gg")

    assert [result.message_id for result in in_live] == [message.message_id]
    assert [result.message_id for result in everywhere] == [message.message_id]
    assert hits.calls == [
        (ItemType.MESSAGE, [message.message_id], "gg"),
        (ItemType.MESSAGE, [message.message_id], "gg"),
    ]
