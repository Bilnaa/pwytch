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


class ReplaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    replay_url: str = "http://localhost:8003"
    replay_timeout_seconds: float = 5


class BookmarksSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bookmarks_url: str = "http://localhost:8005"
    bookmarks_timeout_seconds: float = 5


class StatsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stats_url: str = "http://localhost:8006"
    stats_timeout_seconds: float = 5


class LiveChatSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    live_chat_url: str = "http://localhost:8002"
    live_chat_timeout_seconds: float = 5

    @property
    def live_chat_ws_url(self) -> str:
        return self.live_chat_url.replace("http", "ws", 1).rstrip("/")

class MqttSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883

class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_origin: str = "http://localhost:5173"


class FrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # build of the web folder (npm run build), relative to main/
    frontend_dir: str = "../web/dist"


db_settings = DbSettings.model_validate({})
auth_settings = AuthSettings.model_validate({})
stream_settings = StreamSettings()
search_settings = SearchSettings()
replay_settings = ReplaySettings()
bookmarks_settings = BookmarksSettings()
stats_settings = StatsSettings()
live_chat_settings = LiveChatSettings()
mqtt_settings = MqttSettings()
cors_settings = CorsSettings()
frontend_settings = FrontendSettings()
