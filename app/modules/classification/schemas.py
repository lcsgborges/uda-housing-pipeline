from typing import Literal

from pydantic import BaseModel, Field, field_validator

ClassificationDomain = Literal[
    "financeiro",
    "operacional",
    "esg",
    "mercado",
    "governanca",
    "outro",
]
ExtractionStrategy = Literal[
    "full_scan",
    "semantic_chunking",
    "sequential_scan",
    "ignore",
    "needs_ocr",
]


class DocumentClassification(BaseModel):
    is_useful: bool
    document_type: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_]+$")
    domains: list[ClassificationDomain] = Field(default_factory=list, max_length=6)
    year: int | None = Field(default=None, ge=2000, le=2100)
    quarter: int | None = Field(default=None, ge=1, le=4)
    extraction_strategy: ExtractionStrategy
    reason: str = Field(min_length=3, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("domains")
    @classmethod
    def normalize_domains(cls, value: list[ClassificationDomain]) -> list[ClassificationDomain]:
        """Remove domínios duplicados preservando a ordem retornada."""
        return list(dict.fromkeys(value))
