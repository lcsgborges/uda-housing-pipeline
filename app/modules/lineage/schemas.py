from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DataLineageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_id: int
    document_id: int
    original_url: str
    file_hash: str
    source_page: int | None
    source_excerpt: str | None
    extraction_model: str
    extraction_prompt_version: str
    extracted_at: datetime
