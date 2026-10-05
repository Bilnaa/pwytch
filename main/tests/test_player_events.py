import logging

import pytest
from common import topics
from common.mqtt import NotConnectedError

from app.dependencies import get_mqtt
from app.main import app
from app.services import player_events
from app.services.player_events import PlayerEventLimiter, TooManyPlayerEventsError
from tests.test_streams_router import PAYLOAD, auth_headers


class FakeMqtt:
    def __init__(self, error=None):
        self.published = []
        self.error = error

    async def publish(self, topic, event):
        if self.error:
            raise self.error
        self.published.append((topic, event))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def limiter(monkeypatch):
    fresh = PlayerEventLimiter(max_events=3, window_seconds=10)
    monkeypatch.setattr(player_events, "limiter", fresh)


@pytest.fixture
def mqtt():
    fake = FakeMqtt()
    app.dependency_overrides[get_mqtt] = lambda: fake
    return fake


@pytest.fixture
def stream_id(client):
    response = client.post("/streams", json=PAYLOAD, headers=auth_headers(client, "streamer"))
    return response.json()["id"]


@pytest.mark.parametrize("event_type", ["play", "pause", "stop"])
def test_event_is_accepted_then_published(client, mqtt, stream_id, event_type):
    response = client.post(
        f"/streams/{stream_id}/player-events", json={"event_type": event_type}
    )

    assert response.status_code == 202
    assert response.content == b""
    [(topic, event)] = mqtt.published
    assert topic == topics.PLAYER_EVENT
    assert event.stream_id == stream_id
    assert event.event_type == event_type
    assert event.user_id is None
    assert event.occurred_at.tzinfo is not None


def test_logged_in_viewer_is_in_the_event(client, mqtt, stream_id):
    headers = auth_headers(client, "viewer")
    viewer_id = client.get("/auth/me", headers=headers).json()["id"]

    response = client.post(
        f"/streams/{stream_id}/player-events", json={"event_type": "play"}, headers=headers
    )

    assert response.status_code == 202
    assert mqtt.published[0][1].user_id == viewer_id


@pytest.mark.parametrize("payload", [{"event_type": "seek"}, {"event_type": None}, {}])
def test_invalid_event_type_gives_422(client, mqtt, stream_id, payload):
    response = client.post(f"/streams/{stream_id}/player-events", json=payload)

    assert response.status_code == 422
    assert mqtt.published == []


def test_unknown_stream_gives_404(client, mqtt):
    response = client.post("/streams/999/player-events", json={"event_type": "play"})

    assert response.status_code == 404
    assert mqtt.published == []


def test_broker_down_still_accepts_and_logs(client, stream_id, caplog):
    app.dependency_overrides[get_mqtt] = lambda: FakeMqtt(NotConnectedError("down"))

    with caplog.at_level(logging.ERROR, logger="app.services.player_events"):
        response = client.post(
            f"/streams/{stream_id}/player-events", json={"event_type": "stop"}
        )

    assert response.status_code == 202
    assert "lost" in caplog.text


def test_too_many_events_give_429_and_are_not_published(client, mqtt, stream_id):
    for _ in range(3):
        client.post(f"/streams/{stream_id}/player-events", json={"event_type": "play"})

    response = client.post(f"/streams/{stream_id}/player-events", json={"event_type": "pause"})

    assert response.status_code == 429
    assert len(mqtt.published) == 3


def test_limit_is_per_stream(client, mqtt, stream_id):
    other = client.post("/streams", json=PAYLOAD, headers=auth_headers(client, "other"))
    for _ in range(3):
        client.post(f"/streams/{stream_id}/player-events", json={"event_type": "play"})

    response = client.post(
        f"/streams/{other.json()['id']}/player-events", json={"event_type": "play"}
    )

    assert response.status_code == 202


def test_limiter_accepts_again_after_the_window():
    clock = FakeClock()
    limiter = PlayerEventLimiter(max_events=2, window_seconds=10, clock=clock)
    limiter.check("1.2.3.4", 1)
    limiter.check("1.2.3.4", 1)

    with pytest.raises(TooManyPlayerEventsError):
        limiter.check("1.2.3.4", 1)

    clock.now = 10.5
    limiter.check("1.2.3.4", 1)


def test_limiter_is_per_client():
    limiter = PlayerEventLimiter(max_events=1, window_seconds=10, clock=FakeClock())
    limiter.check("1.2.3.4", 1)

    limiter.check("5.6.7.8", 1)


def test_limiter_forgets_clients_after_the_window():
    clock = FakeClock()
    limiter = PlayerEventLimiter(max_events=1, window_seconds=10, clock=clock)
    limiter.check("1.2.3.4", 1)

    clock.now = 11
    limiter.check("5.6.7.8", 1)

    assert list(limiter.sent) == [("5.6.7.8", 1)]
