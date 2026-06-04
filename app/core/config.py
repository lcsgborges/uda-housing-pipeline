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

    llm_provider: str = "ollama"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    extraction_prompt_version: str = "v1"
    extraction_batch_size: int = Field(default=5, ge=1, le=50)

    request_timeout_seconds: int = Field(default=20, ge=3)
    user_agent: str = "Pipeline-UDA/1.0"
    enable_ingestion_scheduler: bool = False
    ingestion_schedule_hour: int = Field(default=2, ge=0, le=23)
    ingestion_schedule_minute: int = Field(default=0, ge=0, le=59)
    scheduler_timezone: str = "America/Sao_Paulo"
    extraction_full_scan_max_chars: int = Field(default=14000, ge=2000)
    extraction_context_max_chars: int = Field(default=18000, ge=4000)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Carrega configurações da aplicação e garante o diretório de documentos."""
    settings = Settings()
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    return settings
