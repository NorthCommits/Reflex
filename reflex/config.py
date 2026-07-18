from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )

    gemini_api_key: str
    model_name: str = "gemini-flash-latest"
    database_url: str
    readonly_database_url: str
    max_attempts: int = 4
    row_limit: int = 200
    statement_timeout_ms: int = 5000
    log_level: str = "INFO"


settings = Settings()
