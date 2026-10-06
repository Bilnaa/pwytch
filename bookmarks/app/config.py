from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://postgres:postgres@localhost:5432/microservices'
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    redis_url: str = "redis://localhost:6379/0"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()