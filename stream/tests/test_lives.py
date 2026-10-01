import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.lives import lives_files

client = TestClient(app)


@pytest.fixture
def lives(tmp_path, monkeypatch):
    lives = tmp_path / "lives"
    (lives / "42").mkdir(parents=True)
    (lives / "42" / "index.m3u8").write_text("#EXTM3U\n")
    (lives / "42" / "index0.ts").write_bytes(b"segment")
    (tmp_path / "secret.txt").write_text("secret")
    monkeypatch.setattr(lives_files, "all_directories", [lives])


def test_playlist_and_segment_are_served(lives):
    playlist = client.get("/lives/42/index.m3u8")
    segment = client.get("/lives/42/index0.ts")

    assert playlist.text == "#EXTM3U\n"
    assert playlist.headers["content-type"] == "application/vnd.apple.mpegurl"
    assert segment.content == b"segment"
    assert segment.headers["content-type"] == "video/mp2t"


def test_missing_file_is_404(lives):
    assert client.get("/lives/42/index9.ts").status_code == 404
    assert client.get("/lives/43/index.m3u8").status_code == 404


def test_cannot_leave_the_lives_folder(lives):
    assert client.get("/lives/%2e%2e/secret.txt").status_code == 404


def test_route_is_in_docs():
    assert "/lives/{stream_id}/{filename}" in client.get("/openapi.json").json()["paths"]
