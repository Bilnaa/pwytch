from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # docker-compose Postgres; tests use their own in-memory SQLite engine.
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/microservices"
    )
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883


settings = Settings()
