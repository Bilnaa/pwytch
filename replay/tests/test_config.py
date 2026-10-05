from pathlib import Path

from app.core.config import Settings


def test_defaults_point_to_the_local_stack(monkeypatch):
    # Toutes les variables vérifiées : une seule définie dans l'environnement casserait le test.
    for name in [
        "DATABASE_URL",
        "LIVES_DIR",
        "REPLAYS_DIR",
        "CONVERSION_TIMEOUT_S",
    ]:
        monkeypatch.delenv(name, raising=False)

    app_settings = Settings(_env_file=None)

    assert app_settings.database_url.endswith("@localhost:5432/replay")
    assert app_settings.lives_dir == Path("../stream/lives")
    assert app_settings.replays_dir == Path("replays")
    assert app_settings.conversion_timeout_s == 600


def test_environment_overrides_the_defaults(monkeypatch):
    monkeypatch.setenv("LIVES_DIR", "/code/lives")
    monkeypatch.setenv("REPLAYS_DIR", "/data/replays")
    monkeypatch.setenv("CONVERSION_TIMEOUT_S", "30")

    app_settings = Settings(_env_file=None)

    assert app_settings.lives_dir == Path("/code/lives")
    assert app_settings.replays_dir == Path("/data/replays")
    assert app_settings.conversion_timeout_s == 30
