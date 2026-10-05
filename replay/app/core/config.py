from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base replay créée par infra/postgres/init.sql ; les tests utilisent SQLite en mémoire.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/replay"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    # stream sert les playlists et les segments HLS, y compris ceux d'un live terminé.
    stream_url: str = "http://localhost:8001"
    replays_dir: Path = Path("replays")
    stream_timeout_s: float = 5
    conversion_timeout_s: float = 600


settings = Settings()
