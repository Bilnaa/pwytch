from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    lives_dir: Path = Path("lives")
    reconnect_seconds: float = 30
    signal_timeout_seconds: float = 10
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883


settings = Settings()
