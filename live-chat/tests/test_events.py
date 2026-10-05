import asyncio
import threading

from common.mqtt import NotConnectedError
from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import wait_joined

client = TestClient(app)


def published(mqtt):
    return [call.args for call in mqtt.publish.await_args_list]


def test_accepted_message_is_published(saved_messages, mqtt):
    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author:
        author.send_json({"content": "  gg wp  "})
        received = author.receive_json()

    [(topic, event)] = published(mqtt)
    assert topic == "chat/message"
    # same message as the one stored and broadcast
    assert event.message_id == saved_messages[0].id
    assert str(event.message_id) == received["id"]
    assert event.model_dump(exclude={"event_id", "version", "message_id", "sent_at"}) == {
        "stream_id": 1,
        "author_id": 7,
        "author_name": "author",
        "content": "gg wp",
    }
    assert event.sent_at == saved_messages[0].sent_at


def test_refused_message_is_not_published(saved_messages, mqtt):
    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author:
        author.send_json({"content": ""})
        assert author.receive_json()["code"] == "EMPTY_MESSAGE"
        author.send_json({"content": "first"})
        author.receive_json()
        author.send_json({"content": "second"})
        assert author.receive_json()["code"] == "RATE_LIMITED"

    assert [event.content for _, event in published(mqtt)] == ["first"]


def test_unsaved_message_is_not_published(database_down, mqtt):
    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author:
        author.send_json({"content": "hello"})
        assert author.receive_json()["code"] == "MESSAGE_NOT_SAVED"

    assert published(mqtt) == []


def test_publication_does_not_delay_the_broadcast(saved_messages, mqtt):
    started = threading.Event()
    finished = []

    async def slow_publish(topic, event):
        started.set()
        await asyncio.sleep(0.5)
        finished.append(event)

    mqtt.publish.side_effect = slow_publish
    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author, \
            client.websocket_connect("/streams/1/chat") as viewer:
        wait_joined(viewer)
        author.send_json({"content": "hello"})
        assert viewer.receive_json()["content"] == "hello"
        # the viewer got the message while the publication was still running
        assert started.wait(timeout=1)
        assert finished == []


def test_broker_down_still_broadcasts(saved_messages, mqtt, caplog):
    mqtt.publish.side_effect = NotConnectedError("Not connected to the MQTT broker")
    with client.websocket_connect("/streams/1/chat?user_id=7&username=author") as author, \
            client.websocket_connect("/streams/1/chat") as viewer:
        wait_joined(viewer)
        author.send_json({"content": "hello"})
        assert viewer.receive_json()["content"] == "hello"
        # the chat keeps working after the failed publication
        author.receive_json()
        author.send_json({"content": ""})
        assert author.receive_json()["code"] == "EMPTY_MESSAGE"

    assert f"Message {saved_messages[0].id} not published" in caplog.text


def test_lifespan_starts_and_stops_the_mqtt_client(mqtt):
    with TestClient(app):
        mqtt.start.assert_awaited_once()
    mqtt.stop.assert_awaited_once()
