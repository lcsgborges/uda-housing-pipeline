import json
from abc import ABC, abstractmethod

from openai import OpenAI

from app.core.config import get_settings
from app.modules.extraction.semantic_contract import get_semantic_contract_json_schema
from app.modules.metrics.schemas import ExtractedMetricBatch


class BaseLLMClient(ABC):
    @abstractmethod
    def extract_metrics(self, *, company: str, original_url: str, context: str, year: int | None, quarter: int | None) -> ExtractedMetricBatch:
        raise NotImplementedError


class FakeLLMClient(BaseLLMClient):
    def extract_metrics(self, *, company: str, original_url: str, context: str, year: int | None, quarter: int | None) -> ExtractedMetricBatch:
        _ = (original_url, context)
        return ExtractedMetricBatch(
            metrics=[
                {
                    "company": company,
                    "period_year": year,
                    "period_quarter": quarter,
                    "metric_name": "vendas_liquidas",
                    "metric_category": "operacional",
                    "value": 123456789.0,
                    "unit": "R$",
                    "currency": "BRL",
                    "source_page": 1,
                    "source_excerpt": "Vendas líquidas totalizaram R$ 123,4 milhões no trimestre.",
                    "confidence": 0.9,
                },
                {
                    "company": company,
                    "period_year": year,
                    "period_quarter": quarter,
                    "metric_name": "lucro_liquido",
                    "metric_category": "financeiro",
                    "value": None,
                    "unit": "R$",
                    "currency": "BRL",
                    "source_page": 2,
                    "source_excerpt": "Não identificado no documento.",
                    "confidence": 0.6,
                },
            ]
        )


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def extract_metrics(self, *, company: str, original_url: str, context: str, year: int | None, quarter: int | None) -> ExtractedMetricBatch:
        schema = get_semantic_contract_json_schema()
        prompt = (
            "Extraia métricas habitacionais e financeiras em JSON válido seguindo estritamente o schema. "
            "Não invente dados: quando não encontrar valor explícito, use null. "
            "Não retorne texto fora de JSON. "
            f"Empresa: {company}. URL: {original_url}. Ano: {year}. Trimestre: {quarter}.\n"
            f"Schema: {json.dumps(schema, ensure_ascii=False)}\n"
            f"Conteúdo:\n{context}"
        )
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0,
        )
        text = response.output_text
        return ExtractedMetricBatch.model_validate_json(text)


def build_llm_client() -> BaseLLMClient:
    settings = get_settings()
    if settings.llm_provider.lower() == "openai":
        return OpenAILLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    return FakeLLMClient()
