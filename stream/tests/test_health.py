from fastapi.testclient import TestClient

from app.main import app
from app.routers import health

client = TestClient(app)


def test_health(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_degraded_without_ffmpeg(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: None)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded"}


def test_degraded_without_broker(mqtt, monkeypatch):
    mqtt.connected = False
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert client.get("/health").json() == {"status": "degraded"}
