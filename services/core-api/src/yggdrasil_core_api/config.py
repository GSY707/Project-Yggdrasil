from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YGGDRASIL_CORE_API_", extra="ignore")

    app_name: str = "Yggdrasil Core API"
    app_version: str = "0.1.0"


settings = Settings()