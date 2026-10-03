from fastapi.testclient import TestClient

from app import live
from app.main import app
from tests.helpers import INFO

client = TestClient(app)


def add_live(monkeypatch, tmp_path, stream_id):
    entry = live.Live(stream_id, tmp_path, live.LiveInfo(**INFO))
    monkeypatch.setitem(live.lives, stream_id, entry)
    return entry


def test_no_lives():
    assert client.get("/streams").json() == []


def test_lists_running_lives_but_not_ending_ones(monkeypatch, tmp_path):
    add_live(monkeypatch, tmp_path, 43)
    add_live(monkeypatch, tmp_path, 42)
    add_live(monkeypatch, tmp_path, 44).ending = object()

    assert client.get("/streams").json() == [42, 43]
