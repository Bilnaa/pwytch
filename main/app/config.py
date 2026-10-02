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

db_settings = DbSettings.model_validate({})
auth_settings = AuthSettings.model_validate({})
stream_settings = StreamSettings()
