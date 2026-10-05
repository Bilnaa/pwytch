from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base replay créée par infra/postgres/init.sql ; les tests utilisent SQLite en mémoire.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/replay"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    # LIVES_DIR de stream (lives/{stream_id}/index.m3u8), lu sans jamais être modifié.
    lives_dir: Path = Path("../stream/lives")
    replays_dir: Path = Path("replays")
    conversion_timeout_s: float = 600


settings = Settings()
