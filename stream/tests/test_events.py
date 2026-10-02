import pytest
from common.mqtt import NotConnectedError
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from tests.helpers import ingest_url, slate, streamer, wait_until, wait_until_finished, written


def published(mqtt):
    return [call.args for call in mqtt.publish.await_args_list]


def test_started_is_published_once_and_ended_when_the_live_is_over(procs, mqtt, monkeypatch):
    monkeypatch.setattr(settings, "reconnect_seconds", 5)
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(30)) as ws:
            ws.close()
        wait_until(lambda: slate(procs))
        with client.websocket_connect(ingest_url(30)) as ws:
            ws.close()
        during_live = [topic for topic, _ in published(mqtt)]

    (_, started), (topic, ended) = published(mqtt)
    assert during_live == ["stream/started"]  # the reconnection published nothing
    assert started.model_dump(exclude={"event_id", "version", "started_at"}) == {
        "stream_id": 30,
        "streamer_id": 1,
        "streamer_name": "alice",
        "title": "Speedrun",
        "game": "Celeste",
    }
    assert topic == "stream/ended"
    assert (ended.stream_id, ended.streamer_id, ended.reason) == (30, 1, "normal")
    assert ended.duration_s == (ended.ended_at - started.started_at).total_seconds() > 0
    mqtt.start.assert_awaited_once()
    mqtt.stop.assert_awaited_once()


def test_ended_waits_for_the_grace_period(procs, mqtt):
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(31)) as ws:
            ws.close()
        wait_until(lambda: slate(procs))
        on_slate = [topic for topic, _ in published(mqtt)]
        wait_until_finished(31)
        after = [topic for topic, _ in published(mqtt)]

    assert on_slate == ["stream/started"]
    assert after == ["stream/started", "stream/ended"]


def test_ffmpeg_crash_publishes_ended_with_error(procs, mqtt):
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(32)) as ws:
            procs[0].returncode = 1  # ffmpeg died
            ws.send_bytes(b"garbage")
            with pytest.raises(WebSocketDisconnect):
                ws.receive_bytes()
        wait_until_finished(32)

    topic, ended = published(mqtt)[-1]
    assert topic == "stream/ended"
    assert ended.reason == "error"


def test_broker_down_does_not_stop_the_live(procs, mqtt, tmp_path, caplog):
    mqtt.publish.side_effect = NotConnectedError("Not connected to the MQTT broker")
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(33)) as ws:
            ws.send_bytes(b"chunk")
            (tmp_path / "33" / "index.m3u8").write_text("#EXTM3U\n")
            ws.close()
        wait_until_finished(33)

    assert written(streamer(procs)[0]) == [b"chunk"]
    assert (tmp_path / "33" / "index.m3u8").read_text() == "#EXTM3U\n#EXT-X-ENDLIST\n"
    assert "Event stream/started not published" in caplog.text
    assert "Event stream/ended not published" in caplog.text
