from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    status: DocumentStatus
    collected_at: datetime
    processed_at: datetime | None
    error_message: str | None
