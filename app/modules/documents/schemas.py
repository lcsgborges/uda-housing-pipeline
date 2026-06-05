from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.modules.documents.models import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str | None
    original_url: str
    local_path: str | None
    file_hash: str | None
    year: int | None
    quarter: int | None
    document_type: str | None
    classification_is_useful: bool | None
    classification_confidence: float | None
    classification_reason: str | None
    classification_model: str | None
    detected_domains: list[str] | None
    extraction_strategy: str | None
    classified_at: datetime | None
    status: DocumentStatus
    collected_at: datetime
    processed_at: datetime | None
    error_message: str | None

    @computed_field
    @property
    def file_url(self) -> str | None:
        """Retorna a URL local da API para abrir o arquivo do documento."""
        if self.local_path is None:
            return None
        return f"/api/documents/{self.id}/file"
