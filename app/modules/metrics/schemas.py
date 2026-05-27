from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExtractedMetric(BaseModel):
    company: str
    period_year: int | None = None
    period_quarter: int | None = Field(default=None, ge=1, le=4)
    metric_name: str
    metric_category: str | None = None
    value: float | None = None
    unit: str | None = None
    currency: str | None = None
    source_page: int | None = None
    source_excerpt: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedMetricBatch(BaseModel):
    metrics: list[ExtractedMetric]


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    document_id: int
    metric_name: str
    metric_category: str | None
    period_year: int | None
    period_quarter: int | None
    value: float | None
    unit: str | None
    currency: str | None
    source_page: int | None
    source_excerpt: str | None
    confidence: float


class ConjunturaMetricItem(BaseModel):
    nome: str
    valor: float | None
    unidade: str | None
    fonte: dict
    confianca: float


class ConjunturaResponse(BaseModel):
    empresa: str
    ano: int
    trimestre: int
    metricas: list[ConjunturaMetricItem]
