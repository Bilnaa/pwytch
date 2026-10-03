from fastapi.testclient import TestClient

from app import live
from app.main import app
from app.routers import health
from tests.helpers import INFO

client = TestClient(app)


def test_health(monkeypatch, tmp_path):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setitem(live.lives, 42, live.Live(42, tmp_path, live.LiveInfo(**INFO)))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "ffmpeg": True, "broker": True, "lives": 1}


def test_degraded_without_ffmpeg_or_broker(mqtt, monkeypatch):
    mqtt.connected = False
    monkeypatch.setattr(health.shutil, "which", lambda name: None)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "ffmpeg": False, "broker": False, "lives": 0}
