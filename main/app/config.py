from pydantic_settings import BaseSettings, SettingsConfigDict

class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

class StreamSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stream_url: str = "http://localhost:8001"
    stream_timeout_seconds: float = 5
    @property
    def stream_ws_url(self) -> str:
        # http -> ws, https -> wss
        return self.stream_url.replace("http", "ws", 1).rstrip("/")

class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    search_url: str = "http://localhost:8004"
    search_timeout_seconds: float = 5

class MqttSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883

class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_origin: str = "http://localhost:5173"


db_settings = DbSettings.model_validate({})
auth_settings = AuthSettings.model_validate({})
stream_settings = StreamSettings()
search_settings = SearchSettings()
mqtt_settings = MqttSettings()
cors_settings = CorsSettings()
