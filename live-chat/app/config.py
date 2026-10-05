from pydantic_settings import BaseSettings, SettingsConfigDict


class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Missing config fails at startup
    database_url: str


db_settings = DbSettings.model_validate({})


class MqttSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883


mqtt_settings = MqttSettings()


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    redis_timeout_seconds: float = 0.5
    # Longest time a message saved while the cache was being filled can be missing from it
    cache_ttl_seconds: int = 60


redis_settings = RedisSettings()
