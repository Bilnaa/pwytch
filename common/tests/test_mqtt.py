import asyncio
from datetime import datetime, timezone

import aiomqtt
import pytest

from common import mqtt, topics
from common.events import StreamEnded
from common.mqtt import MqttClient, NotConnectedError

NOW = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)


def ended(stream_id=1) -> StreamEnded:
    return StreamEnded(
        stream_id=stream_id, streamer_id=2, ended_at=NOW, duration_s=3, reason="normal"
    )


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)


@pytest.fixture
def client():
    return MqttClient(reconnect_seconds=0)


async def test_valid_message_reaches_the_handler(client):
    recorder = Recorder()
    client.subscribe(topics.STREAM_ENDED, StreamEnded, recorder)
    event = ended()

    await client.handle(topics.STREAM_ENDED, event.model_dump_json().encode())

    assert recorder.events == [event]


async def test_invalid_message_is_ignored(client):
    recorder = Recorder()
    client.subscribe(topics.STREAM_ENDED, StreamEnded, recorder)

    await client.handle(topics.STREAM_ENDED, b"not json")
    await client.handle(topics.STREAM_ENDED, b'{"stream_id": 1}')

    assert recorder.events == []


async def test_message_on_an_unknown_topic_is_ignored(client):
    recorder = Recorder()
    client.subscribe(topics.STREAM_ENDED, StreamEnded, recorder)

    await client.handle(topics.STREAM_STARTED, ended().model_dump_json())

    assert recorder.events == []


async def test_duplicate_event_is_handled_once(client):
    recorder = Recorder()
    client.subscribe(topics.STREAM_ENDED, StreamEnded, recorder)
    payload = ended().model_dump_json()

    await client.handle(topics.STREAM_ENDED, payload)
    await client.handle(topics.STREAM_ENDED, payload)

    assert len(recorder.events) == 1


async def test_different_events_are_all_handled(client):
    recorder = Recorder()
    client.subscribe(topics.STREAM_ENDED, StreamEnded, recorder)

    await client.handle(topics.STREAM_ENDED, ended(1).model_dump_json())
    await client.handle(topics.STREAM_ENDED, ended(2).model_dump_json())

    assert len(recorder.events) == 2


async def test_old_event_ids_are_forgotten():
    client = MqttClient(dedup_size=2)
    recorder = Recorder()
    client.subscribe(topics.STREAM_ENDED, StreamEnded, recorder)
    first = ended(1).model_dump_json()

    await client.handle(topics.STREAM_ENDED, first)
    await client.handle(topics.STREAM_ENDED, ended(2).model_dump_json())
    await client.handle(topics.STREAM_ENDED, ended(3).model_dump_json())
    await client.handle(topics.STREAM_ENDED, first)

    assert len(recorder.events) == 4


async def test_failing_handler_does_not_stop_the_consumer(client):
    calls = []

    async def handler(event):
        calls.append(event)
        raise RuntimeError("boom")

    client.subscribe(topics.STREAM_ENDED, StreamEnded, handler)

    await client.handle(topics.STREAM_ENDED, ended(1).model_dump_json())
    await client.handle(topics.STREAM_ENDED, ended(2).model_dump_json())

    assert len(calls) == 2


async def test_failed_event_is_handled_again_when_sent_again(client):
    calls = []

    async def handler(event):
        calls.append(event)
        if len(calls) == 1:
            raise RuntimeError("database down")

    client.subscribe(topics.STREAM_ENDED, StreamEnded, handler)
    payload = ended().model_dump_json()

    await client.handle(topics.STREAM_ENDED, payload)
    await client.handle(topics.STREAM_ENDED, payload)
    await client.handle(topics.STREAM_ENDED, payload)

    assert len(calls) == 2


async def test_publish_without_connection_raises(client):
    with pytest.raises(NotConnectedError):
        await client.publish(topics.STREAM_ENDED, ended())


class FakeBroker:
    """Replaces aiomqtt.Client: the first `failures` connections are refused."""

    def __init__(self, failures=0, messages=()):
        self.failures = failures
        self.messages = list(messages)
        self.connections = 0
        self.subscribed = []
        self.published = []
        self.connected = asyncio.Event()
        self.clean_session = None

    def __call__(self, host, port, identifier=None, clean_session=None):
        broker = self
        broker.clean_session = clean_session

        class FakeClient:
            async def __aenter__(self):
                broker.connections += 1
                if broker.connections <= broker.failures:
                    raise aiomqtt.MqttError("refused")
                broker.connected.set()
                return self

            async def __aexit__(self, *exc):
                return False

            async def subscribe(self, topic, qos):
                broker.subscribed.append((topic, qos))

            async def publish(self, topic, payload, qos):
                broker.published.append((topic, payload, qos))

            @property
            def messages(self):
                return self._messages()

            async def _messages(self):
                for message in broker.messages:
                    yield message
                await asyncio.Event().wait()

        return FakeClient()


class FakeMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


async def test_client_retries_until_the_broker_answers(monkeypatch, client):
    broker = FakeBroker(failures=2)
    monkeypatch.setattr(mqtt.aiomqtt, "Client", broker)

    await client.start()
    await asyncio.wait_for(broker.connected.wait(), timeout=2)
    await client.stop()

    assert broker.connections == 3


async def test_session_is_persistent_with_a_client_id(monkeypatch):
    broker = FakeBroker()
    monkeypatch.setattr(mqtt.aiomqtt, "Client", broker)
    client = MqttClient(client_id="main", reconnect_seconds=0)

    await client.start()
    await asyncio.wait_for(broker.connected.wait(), timeout=2)
    await client.stop()

    assert broker.clean_session is False


async def test_session_is_clean_without_a_client_id(monkeypatch, client):
    broker = FakeBroker()
    monkeypatch.setattr(mqtt.aiomqtt, "Client", broker)

    await client.start()
    await asyncio.wait_for(broker.connected.wait(), timeout=2)
    await client.stop()

    assert broker.clean_session is True


async def test_subscriptions_are_sent_with_qos_1(monkeypatch, client):
    broker = FakeBroker()
    monkeypatch.setattr(mqtt.aiomqtt, "Client", broker)
    client.subscribe(topics.STREAM_ENDED, StreamEnded, Recorder())

    await client.start()
    await asyncio.wait_for(broker.connected.wait(), timeout=2)
    await client.stop()

    assert broker.subscribed == [(topics.STREAM_ENDED, 1)]


async def test_received_messages_reach_the_handler(monkeypatch, client):
    event = ended()
    broker = FakeBroker(messages=[FakeMessage(topics.STREAM_ENDED, event.model_dump_json())])
    monkeypatch.setattr(mqtt.aiomqtt, "Client", broker)
    recorder = Recorder()
    client.subscribe(topics.STREAM_ENDED, StreamEnded, recorder)

    await client.start()
    await asyncio.wait_for(broker.connected.wait(), timeout=2)
    await asyncio.sleep(0)
    await client.stop()

    assert recorder.events == [event]


async def test_publish_sends_the_event_with_qos_1(monkeypatch, client):
    broker = FakeBroker()
    monkeypatch.setattr(mqtt.aiomqtt, "Client", broker)
    event = ended()

    await client.start()
    await asyncio.wait_for(broker.connected.wait(), timeout=2)
    await client.publish(topics.STREAM_ENDED, event)
    await client.stop()

    assert broker.published == [(topics.STREAM_ENDED, event.model_dump_json(), 1)]


async def test_client_is_not_connected_after_stop(monkeypatch, client):
    broker = FakeBroker()
    monkeypatch.setattr(mqtt.aiomqtt, "Client", broker)

    await client.start()
    await asyncio.wait_for(broker.connected.wait(), timeout=2)
    assert client.connected
    await client.stop()

    assert not client.connected
