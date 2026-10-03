import logging
from unittest.mock import AsyncMock, call

import pytest
from app.hits import message_hits, publish_hits, streamer_hits
from app.schemas import MessageResult, StreamerResult
from common.events import ItemType
from common.mqtt import MqttClient, NotConnectedError
from common.topics import SEARCH_HIT

from tests.factories import FIRST_START, MESSAGE_ID

HIT_AT = FIRST_START


def error_records(caplog):
    return [record for record in caplog.records if record.levelno == logging.ERROR]


def make_streamer_result(streamer_id: int) -> StreamerResult:
    return StreamerResult(
        streamer_id=streamer_id,
        streamer_name=f"Zera {streamer_id}",
        last_title=None,
        last_game=None,
        is_live=False,
        live_stream_id=None,
    )


def make_message_result() -> MessageResult:
    return MessageResult(
        message_id=MESSAGE_ID,
        stream_id=1,
        author_name="Célèste",
        content="GG WP !",
        sent_at=FIRST_START,
    )


def make_hits(count: int):
    results = [make_streamer_result(streamer_id) for streamer_id in range(1, count + 1)]
    return streamer_hits(results, "zera", HIT_AT)


# Construction des hits


def test_streamer_hits_keep_the_order_of_the_results():
    results = [make_streamer_result(42), make_streamer_result(7)]

    hits = streamer_hits(results, "zera", HIT_AT)

    assert [hit.item_id for hit in hits] == ["42", "7"]
    assert all(hit.item_type is ItemType.STREAMER for hit in hits)
    assert all(hit.query == "zera" and hit.hit_at == HIT_AT for hit in hits)


def test_message_hits_use_the_message_id_as_text():
    [hit] = message_hits([make_message_result()], "gg", HIT_AT)

    assert hit.item_type is ItemType.MESSAGE
    assert hit.item_id == str(MESSAGE_ID)
    assert hit.query == "gg"
    assert hit.hit_at == HIT_AT


def test_no_result_gives_no_hit():
    assert streamer_hits([], "zera", HIT_AT) == []
    assert message_hits([], "gg", HIT_AT) == []


# Publication


@pytest.mark.anyio
async def test_every_hit_is_published_in_order():
    fake_mqtt = AsyncMock(spec=MqttClient)
    hits = make_hits(3)

    await publish_hits(fake_mqtt, hits)

    assert fake_mqtt.publish.await_args_list == [call(SEARCH_HIT, hit) for hit in hits]


@pytest.mark.anyio
async def test_broker_down_stops_at_the_first_failure_with_one_error(caplog):
    fake_mqtt = AsyncMock(spec=MqttClient)
    fake_mqtt.publish.side_effect = [None, None, NotConnectedError("down"), None, None]

    await publish_hits(fake_mqtt, make_hits(5))

    assert fake_mqtt.publish.await_count == 3
    [error] = error_records(caplog)
    assert error.getMessage() == "3 search/hit events not published: down"


@pytest.mark.anyio
async def test_unexpected_error_is_logged_with_its_traceback(caplog):
    fake_mqtt = AsyncMock(spec=MqttClient)
    fake_mqtt.publish.side_effect = RuntimeError("boom")

    await publish_hits(fake_mqtt, make_hits(2))

    assert fake_mqtt.publish.await_count == 1
    [error] = error_records(caplog)
    assert error.exc_info is not None
