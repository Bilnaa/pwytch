import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import live
from app.config import settings
from app.live import LiveInfo
from app.main import app
from tests.helpers import ingest_url, slate, wait_until


def test_live_keeps_the_info_of_the_first_connection(procs, monkeypatch):
    monkeypatch.setattr(settings, "reconnect_seconds", 5)
    with TestClient(app) as client:
        with client.websocket_connect(ingest_url(20)) as ws:
            ws.close()
        wait_until(lambda: slate(procs))
        with client.websocket_connect(ingest_url(20, title="Other title")) as ws:
            info = live.lives[20].info
            ws.close()

    assert info == LiveInfo(streamer_id=1, streamer_name="alice", title="Speedrun", game="Celeste")


def test_websocket_without_info_is_refused(procs):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/streams/21/ingest"):
                pass

    assert exc.value.code == 1008
    assert procs == []


def test_http_ingest_has_default_info(procs):
    with TestClient(app) as client:
        with client.stream("POST", "/streams/22/ingest?title=Demo", content=b"video"):
            info = live.lives[22].info

    assert info == LiveInfo(streamer_id=0, streamer_name="dev", title="Demo", game="Dev")
