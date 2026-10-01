from pydantic_settings import BaseSettings, SettingsConfigDict

class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str

db_settings = DbSettings.model_validate({})