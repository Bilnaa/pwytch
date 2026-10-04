from pathlib import Path

from app.infra.config import Settings


def test_defaults_point_to_the_local_stack(monkeypatch):
    # Toutes les variables vérifiées : une seule définie dans l'environnement casserait le test.
    for name in [
        "DATABASE_URL",
        "STREAM_URL",
        "REPLAYS_DIR",
        "STREAM_TIMEOUT_S",
        "CONVERSION_TIMEOUT_S",
    ]:
        monkeypatch.delenv(name, raising=False)

    app_settings = Settings(_env_file=None)

    assert app_settings.database_url.endswith("@localhost:5432/replay")
    assert app_settings.stream_url == "http://localhost:8001"
    assert app_settings.replays_dir == Path("replays")
    assert app_settings.stream_timeout_s == 5
    assert app_settings.conversion_timeout_s == 600


def test_environment_overrides_the_defaults(monkeypatch):
    monkeypatch.setenv("STREAM_URL", "http://stream:8000")
    monkeypatch.setenv("REPLAYS_DIR", "/data/replays")
    monkeypatch.setenv("CONVERSION_TIMEOUT_S", "30")

    app_settings = Settings(_env_file=None)

    assert app_settings.stream_url == "http://stream:8000"
    assert app_settings.replays_dir == Path("/data/replays")
    assert app_settings.conversion_timeout_s == 30
