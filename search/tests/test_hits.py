import logging
from unittest.mock import AsyncMock, call

import pytest
from app.hits import build_hits, publish_hits
from common.events import ItemType
from common.mqtt import MqttClient, NotConnectedError
from common.topics import SEARCH_HIT

from tests.factories import FIRST_START, MESSAGE_ID

HIT_AT = FIRST_START


def error_records(caplog):
    return [record for record in caplog.records if record.levelno == logging.ERROR]


def make_hits(count: int):
    return build_hits(ItemType.STREAMER, range(1, count + 1), "zera", HIT_AT)


# Construction des hits


def test_hits_keep_the_order_of_the_ids():
    hits = build_hits(ItemType.STREAMER, [42, 7], "zera", HIT_AT)

    assert [hit.item_id for hit in hits] == ["42", "7"]
    assert [hit.item_type for hit in hits] == [ItemType.STREAMER, ItemType.STREAMER]
    assert [hit.query for hit in hits] == ["zera", "zera"]
    assert [hit.hit_at for hit in hits] == [HIT_AT, HIT_AT]


def test_message_uuid_becomes_a_text_item_id():
    [hit] = build_hits(ItemType.MESSAGE, [MESSAGE_ID], "gg", HIT_AT)

    assert hit.item_type is ItemType.MESSAGE
    assert hit.item_id == str(MESSAGE_ID)
    assert hit.query == "gg"
    assert hit.hit_at == HIT_AT


def test_no_id_gives_no_hit():
    assert build_hits(ItemType.STREAMER, [], "zera", HIT_AT) == []


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
