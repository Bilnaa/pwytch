import os
import time
from datetime import datetime, timezone

import pytest
from common.events import StreamStarted
from fastapi.testclient import TestClient

from app import live, recovery
from app.config import settings
from app.main import app
from tests.helpers import INFO, ingest_url, wait_until, wait_until_finished

STARTED_AT = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
OPEN = "#EXTM3U\n#EXTINF:4.000000,\nindex0.ts\n"


@pytest.fixture
def lives_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "lives_dir", tmp_path)
    return tmp_path


def add_live(lives_dir, stream_id, playlist, started=True):
    folder = lives_dir / str(stream_id)
    folder.mkdir()
    (folder / "index.m3u8").write_text(playlist)
    # ffmpeg wrote its last segment 90 s after the start
    last_write = STARTED_AT.timestamp() + 90
    os.utime(folder / "index.m3u8", (last_write, last_write))
    if started:
        event = StreamStarted(stream_id=stream_id, started_at=STARTED_AT, **INFO)
        (folder / "started.json").write_text(event.model_dump_json())
    return folder / "index.m3u8"


def test_interrupted_lives_are_ended_at_startup(lives_dir, mqtt):
    cut = add_live(lives_dir, 40, OPEN)
    over = add_live(lives_dir, 41, OPEN + "#EXT-X-ENDLIST\n")
    unknown = add_live(lives_dir, 42, OPEN, started=False)
    broken = add_live(lives_dir, 45, OPEN)
    broken.with_name("started.json").write_text('{"stream_id": 4')  # cut while being written

    with TestClient(app):
        wait_until(lambda: mqtt.publish.await_count)

    assert cut.read_text() == OPEN + "#EXT-X-ENDLIST\n"
    assert over.read_text() == OPEN + "#EXT-X-ENDLIST\n"
    assert unknown.read_text() == OPEN + "#EXT-X-ENDLIST\n"
    assert broken.read_text() == OPEN + "#EXT-X-ENDLIST\n"
    ((topic, ended),) = [call.args for call in mqtt.publish.await_args_list]
    assert topic == "stream/ended"
    assert (ended.stream_id, ended.streamer_id, ended.reason) == (40, 1, "error")
    assert ended.duration_s == 90


def test_ended_waits_for_the_broker(lives_dir, mqtt, monkeypatch):
    monkeypatch.setattr(recovery, "BROKER_POLL_SECONDS", 0.01)
    mqtt.connected = False
    add_live(lives_dir, 43, OPEN)

    with TestClient(app):
        time.sleep(0.1)
        before = mqtt.publish.await_count
        mqtt.connected = True
        wait_until(lambda: mqtt.publish.await_count)

    assert before == 0
    assert mqtt.publish.await_count == 1


def test_started_event_is_kept_in_the_live_folder(procs, mqtt, tmp_path):
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(44)) as ws:
            ws.close()

    saved = StreamStarted.model_validate_json((tmp_path / "44" / "started.json").read_text())
    assert saved == mqtt.publish.await_args_list[0].args[1]


def test_live_goes_on_when_the_started_file_cannot_be_written(procs, mqtt, monkeypatch):
    monkeypatch.setattr(live, "STARTED_FILE", "missing/started.json")
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(46)) as ws:
            ws.close()
        wait_until_finished(46)

    assert [call.args[0] for call in mqtt.publish.await_args_list] == [
        "stream/started",
        "stream/ended",
    ]
