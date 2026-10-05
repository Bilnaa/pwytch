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
