from pydantic import BaseModel, ConfigDict, Field


class ExtractedMetric(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    period_year: int | None = Field(default=None, ge=2000, le=2100)
    period_quarter: int | None = Field(default=None, ge=1, le=4)
    period_label: str | None = Field(default=None, max_length=80)
    metric_name: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9_]+$")
    metric_category: str | None = Field(default=None, max_length=100)
    raw_label: str | None = Field(default=None, max_length=200)
    dimension: str | None = Field(default=None, max_length=200)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=30)
    currency: str | None = Field(default=None, max_length=10)
    source_page: int | None = Field(default=None, ge=1)
    source_excerpt: str | None = Field(default=None, max_length=1200)
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedInsight(BaseModel):
    insight_type: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_]+$")
    topic: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9_]+$")
    summary: str = Field(min_length=5, max_length=1200)
    value_text: str | None = Field(default=None, max_length=300)
    period_year: int | None = Field(default=None, ge=2000, le=2100)
    period_quarter: int | None = Field(default=None, ge=1, le=4)
    source_page: int | None = Field(default=None, ge=1)
    source_excerpt: str | None = Field(default=None, max_length=1200)
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedMetricBatch(BaseModel):
    metrics: list[ExtractedMetric]
    insights: list[ExtractedInsight] = Field(default_factory=list)


class ExtractedDocumentMetrics(BaseModel):
    document_ref: str
    metrics: list[ExtractedMetric]
    insights: list[ExtractedInsight] = Field(default_factory=list)


class ExtractedBatchResponse(BaseModel):
    documents: list[ExtractedDocumentMetrics]


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    document_id: int
    metric_name: str
    metric_category: str | None
    period_year: int | None
    period_quarter: int | None
    period_label: str | None
    raw_label: str | None
    dimension: str | None
    value: float | None
    unit: str | None
    currency: str | None
    source_page: int | None
    source_excerpt: str | None
    confidence: float


class ConjunturaQuality(BaseModel):
    camada: str
    nivel: str
    score: int


class ConjunturaMetricItem(BaseModel):
    nome: str
    categoria: str | None
    valor: float | None
    unidade: str | None
    fonte: dict
    confianca: float
    qualidade: ConjunturaQuality


class ConjunturaResponse(BaseModel):
    empresa: str
    ano: int
    trimestre: int
    metricas: list[ConjunturaMetricItem]
