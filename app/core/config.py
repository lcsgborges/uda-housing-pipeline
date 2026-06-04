from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Pipeline UDA"
    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://uda:uda@localhost:5432/uda"
    documents_dir: Path = Path("./data/documents")
    log_level: str = "INFO"
    storage_backend: str = "local"
    rustfs_endpoint: str = "localhost:9000"
    rustfs_access_key: str = "rustfsadmin"
    rustfs_secret_key: str = "rustfsadmin"
    rustfs_bucket: str = "uda-documents"
    rustfs_secure: bool = False

    llm_provider: str = "fake"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    extraction_prompt_version: str = "v1"
    extraction_batch_size: int = Field(default=5, ge=1, le=50)

    request_timeout_seconds: int = Field(default=20, ge=3)
    user_agent: str = "Pipeline-UDA/1.0"
    ingestion_poll_interval_minutes: int = Field(default=1440, ge=5)
    enable_ingestion_scheduler: bool = False
    extraction_full_scan_max_chars: int = Field(default=14000, ge=2000)
    extraction_context_max_chars: int = Field(default=18000, ge=4000)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Carrega configurações da aplicação e garante o diretório de documentos."""
    settings = Settings()
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    return settings
