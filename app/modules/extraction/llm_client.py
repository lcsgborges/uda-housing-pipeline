import json
from abc import ABC, abstractmethod

from openai import OpenAI

from app.core.config import get_settings
from app.modules.metrics.schemas import (
    ExtractedBatchResponse,
    ExtractedMetricBatch,
)

SYSTEM_PROMPT = """
Você é um módulo UDA para relatórios de incorporadoras brasileiras.
Você receberá texto integral de PDFs curtos ou chunks semânticos de PDFs longos.
Extraia apenas métricas explícitas no contexto enviado.
Priorize valores absolutos reportados pela empresa; ignore percentuais de variação quando eles forem
apenas comparativos de marketing.
Se o documento for um boletim de conjuntura ou uma tabela comparativa cujo valor principal seja uma
variação percentual, extraia esse percentual como dado válido usando unit="%".
Não calcule, estime ou invente valores. Quando uma métrica não estiver explícita, use null.
Preserve ano/trimestre informados no payload quando o documento não trouxer período melhor.
Use nomes de métricas em snake_case, por exemplo vendas_liquidas, vgv_lancado, unidades_vendidas.
Inclua source_page e source_excerpt sempre que possível para sustentar a linhagem.
O source_excerpt deve ser curto e conter o trecho exato que justifica o valor.
""".strip()


class BaseLLMClient(ABC):
    @abstractmethod
    def extract_metrics(
        self,
        *,
        company: str,
        original_url: str,
        context: str,
        year: int | None,
        quarter: int | None,
    ) -> ExtractedMetricBatch:
        raise NotImplementedError

    @abstractmethod
    def extract_metrics_batch(self, payloads: list[dict]) -> ExtractedBatchResponse:
        raise NotImplementedError


class FakeLLMClient(BaseLLMClient):
    def extract_metrics(
        self,
        *,
        company: str,
        original_url: str,
        context: str,
        year: int | None,
        quarter: int | None,
    ) -> ExtractedMetricBatch:
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

    def extract_metrics_batch(self, payloads: list[dict]) -> ExtractedBatchResponse:
        docs = []
        for payload in payloads:
            docs.append(
                {
                    "document_ref": payload["document_ref"],
                    "metrics": self.extract_metrics(
                        company=payload["company"],
                        original_url=payload["original_url"],
                        context=payload["context"],
                        year=payload.get("year"),
                        quarter=payload.get("quarter"),
                    ).metrics,
                }
            )
        return ExtractedBatchResponse.model_validate({"documents": docs})


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY precisa estar configurada para LLM_PROVIDER=openai.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def extract_metrics(
        self,
        *,
        company: str,
        original_url: str,
        context: str,
        year: int | None,
        quarter: int | None,
    ) -> ExtractedMetricBatch:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_single_document_prompt(
                        company=company,
                        original_url=original_url,
                        context=context,
                        year=year,
                        quarter=quarter,
                    ),
                },
            ],
            text_format=ExtractedMetricBatch,
            temperature=0,
        )
        if response.output_parsed is None:
            raise ValueError("OpenAI não retornou payload estruturado para o contrato semântico.")
        return response.output_parsed

    def extract_metrics_batch(self, payloads: list[dict]) -> ExtractedBatchResponse:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_batch_prompt(payloads),
                },
            ],
            text_format=ExtractedBatchResponse,
            temperature=0,
        )
        if response.output_parsed is None:
            raise ValueError("OpenAI não retornou payload estruturado para o contrato semântico.")
        return response.output_parsed


def build_llm_client() -> BaseLLMClient:
    settings = get_settings()
    if settings.llm_provider.lower() in {"openai", "chatgpt"}:
        return OpenAILLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    return FakeLLMClient()


def _build_single_document_prompt(
    *,
    company: str,
    original_url: str,
    context: str,
    year: int | None,
    quarter: int | None,
) -> str:
    return f"""
Extraia as métricas do documento abaixo.

Empresa: {company}
URL original: {original_url}
Ano inferido: {year}
Trimestre inferido: {quarter}

Conteúdo do documento:
{context}
""".strip()


def _build_batch_prompt(payloads: list[dict]) -> str:
    return f"""
Extraia as métricas dos documentos abaixo.
Para cada documento, copie o document_ref recebido para a resposta correspondente.

Documentos:
{json.dumps(payloads, ensure_ascii=False)}
""".strip()
