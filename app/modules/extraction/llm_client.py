import json
from abc import ABC, abstractmethod

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.modules.metrics.catalog import metric_catalog_prompt
from app.modules.metrics.schemas import (
    ExtractedBatchResponse,
    ExtractedMetricBatch,
)

SYSTEM_PROMPT = f"""
Você é um módulo UDA para relatórios de incorporadoras brasileiras.
Você receberá texto integral de PDFs curtos ou chunks semânticos de PDFs longos.
Extraia apenas métricas explícitas no contexto enviado.
Priorize valores absolutos reportados pela empresa; ignore percentuais de variação quando eles forem
apenas comparativos de marketing.
Se o documento for um boletim de conjuntura ou uma tabela comparativa cujo valor principal seja uma
variação percentual, extraia esse percentual como dado válido usando unit="%".
Não calcule, estime ou invente valores. Quando uma métrica não estiver explícita, use null.
Preserve ano/trimestre informados no payload quando o documento não trouxer período melhor.
Use preferencialmente os nomes canônicos do catálogo abaixo. Se houver sinônimo, responda com o nome
canônico; se encontrar uma métrica fora do catálogo, crie um nome em snake_case claro e específico.

Catálogo de métricas:
{metric_catalog_prompt()}

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
        """Extrai métricas estruturadas de um único contexto documental."""
        raise NotImplementedError

    @abstractmethod
    def extract_metrics_batch(self, payloads: list[dict]) -> ExtractedBatchResponse:
        """Extrai métricas estruturadas de vários documentos em uma chamada."""
        raise NotImplementedError


class OllamaLLMClient(BaseLLMClient):
    def __init__(self, *, base_url: str, model: str, timeout: int):
        """Inicializa o cliente Ollama local sem fazer chamada de rede."""
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def extract_metrics(
        self,
        *,
        company: str,
        original_url: str,
        context: str,
        year: int | None,
        quarter: int | None,
    ) -> ExtractedMetricBatch:
        """Extrai métricas de um documento usando a API local do Ollama."""
        response = self._chat(
            user_prompt=_build_single_document_prompt(
                company=company,
                original_url=original_url,
                context=context,
                year=year,
                quarter=quarter,
            ),
            schema=ExtractedMetricBatch.model_json_schema(),
        )
        return ExtractedMetricBatch.model_validate_json(response)

    def extract_metrics_batch(self, payloads: list[dict]) -> ExtractedBatchResponse:
        """Processa payloads sequencialmente no Ollama, sem chamada batch remota."""
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

    def _chat(self, *, user_prompt: str, schema: dict) -> str:
        """Envia uma conversa ao Ollama e retorna o conteúdo textual da resposta."""
        payload = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        content = response.json().get("message", {}).get("content")
        if not content:
            raise ValueError("Ollama não retornou conteúdo para o contrato semântico.")
        return content


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        """Inicializa o cliente OpenAI validando chave e modelo configurados."""
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
        """Extrai métricas de um documento usando Structured Outputs da OpenAI."""
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
        """Extrai métricas de múltiplos documentos usando Structured Outputs."""
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
    """Constrói o cliente LLM conforme o provider configurado."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider in {"openai", "chatgpt"}:
        return OpenAILLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    if provider == "ollama":
        return OllamaLLMClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.request_timeout_seconds,
        )
    raise ValueError("LLM_PROVIDER deve ser 'openai' ou 'ollama'.")


def _build_single_document_prompt(
    *,
    company: str,
    original_url: str,
    context: str,
    year: int | None,
    quarter: int | None,
) -> str:
    """Monta o prompt de usuário para um único documento."""
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
    """Monta o prompt de usuário para extração em lote."""
    return f"""
Extraia as métricas dos documentos abaixo.
Para cada documento, copie o document_ref recebido para a resposta correspondente.

Documentos:
{json.dumps(payloads, ensure_ascii=False)}
""".strip()
