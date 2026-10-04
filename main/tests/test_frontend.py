import importlib

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import frontend_settings

PAGE = {"Accept": "text/html"}


@pytest.fixture
def load_main(tmp_path, monkeypatch):
    # the front is mounted when app.main is imported, so it is reloaded with another folder
    def load(with_build=True):
        build = tmp_path / "dist"
        if with_build:
            build.mkdir()
            (build / "index.html").write_text("<div id='root'></div>")
        monkeypatch.setattr(frontend_settings, "frontend_dir", str(build))
        return TestClient(importlib.reload(main_module).app)

    yield load
    monkeypatch.undo()
    importlib.reload(main_module)


def test_a_page_reload_gets_the_front(load_main):
    response = load_main().get("/login", headers=PAGE)

    assert response.status_code == 200
    assert "<div id='root'></div>" in response.text


def test_api_routes_come_before_the_front(load_main):
    response = load_main().get("/api", headers=PAGE)

    assert response.json() == {"service": "main"}


def test_an_unknown_api_route_is_a_json_404(load_main):
    response = load_main().get("/api/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_main_starts_without_a_front_build(load_main):
    client = load_main(with_build=False)

    assert client.get("/login", headers=PAGE).status_code == 404
    assert client.get("/api").json() == {"service": "main"}
