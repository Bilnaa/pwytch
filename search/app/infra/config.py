from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres du docker-compose ; les tests utilisent leur propre SQLite en mémoire.
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/microservices"
    )
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883


settings = Settings()
