from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://postgres:postgres@localhost:5432/microservices'

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()