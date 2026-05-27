from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Pipeline UDA"
    app_env: str = "dev"
    database_url: str = "sqlite:///./pipeline_uda.db"
    documents_dir: Path = Path("./data/documents")
    log_level: str = "INFO"

    llm_provider: str = "fake"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    extraction_prompt_version: str = "v1"

    request_timeout_seconds: int = Field(default=20, ge=3)
    user_agent: str = "Pipeline-UDA/1.0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    return settings
