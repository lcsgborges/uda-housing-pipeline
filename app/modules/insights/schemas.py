from pydantic import BaseModel, ConfigDict


class DocumentInsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    document_id: int
    insight_type: str
    topic: str
    summary: str
    value_text: str | None
    period_year: int | None
    period_quarter: int | None
    source_page: int | None
    source_excerpt: str | None
    confidence: float
