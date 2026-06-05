import json
from abc import ABC, abstractmethod

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.modules.classification.schemas import DocumentClassification
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
Se o documento for relatório de sustentabilidade/ESG, extraia indicadores ambientais, sociais,
governança e GRI quando houver valor explícito, incluindo emissões, água, energia, resíduos,
segurança do trabalho, diversidade e valor econômico gerado.
Não calcule, estime ou invente valores. Quando uma métrica não estiver explícita, use null.
Preserve ano/trimestre informados no payload quando o documento não trouxer período melhor.
Use preferencialmente os nomes canônicos do catálogo abaixo. Se houver sinônimo, responda com o nome
canônico; se encontrar uma métrica fora do catálogo, crie um nome em snake_case claro e específico.

Catálogo de métricas:
{metric_catalog_prompt()}

Inclua source_page e source_excerpt sempre que possível para sustentar a linhagem.
O source_excerpt deve ser curto e conter o trecho exato que justifica o valor.
""".strip()

CLASSIFICATION_SYSTEM_PROMPT = """
Você classifica PDFs de Relações com Investidores e sustentabilidade de incorporadoras.
Sua tarefa é decidir se há dados quantitativos úteis para extração estruturada.

Considere útil quando o contexto trouxer métricas explícitas financeiras, operacionais, ESG,
governança, mercado imobiliário ou indicadores GRI com valores numéricos.
Considere não útil quando o material for apenas institucional, publicidade, comunicado sem dados,
glossário, aviso legal, menu, capa ou página sem evidência quantitativa.
Use needs_ocr quando o texto extraído for insuficiente para decidir ou parecer PDF escaneado.

Escolha document_type em snake_case, por exemplo: resultado_trimestral, previa_operacional,
relatorio_sustentabilidade, boletim_conjuntura, comunicado, assembleia, outro.
Escolha extraction_strategy:
- full_scan para documentos curtos e úteis;
- semantic_chunking para documentos longos e úteis;
- ignore para documentos sem dados úteis;
- needs_ocr quando o texto extraído for insuficiente.

Não invente ano/trimestre. Preserve null quando não houver evidência.
Responda somente pelo contrato estruturado.
""".strip()


class BaseLLMClient(ABC):
    @abstractmethod
    def classify_document(
        self,
        *,
        company: str,
        title: str | None,
        original_url: str,
        document_type: str | None,
        year: int | None,
        quarter: int | None,
        pages_count: int,
        text_chars: int,
        context: str,
    ) -> DocumentClassification:
        """Classifica se um documento contém dados úteis para extração."""
        raise NotImplementedError

    @abstractmethod
    def extract_metrics(
        self,
        *,
        company: str,
        original_url: str,
        context: str,
        year: int | None,
        quarter: int | None,
        title: str | None = None,
        document_type: str | None = None,
    ) -> ExtractedMetricBatch:
        """Extrai métricas estruturadas de um único contexto documental."""
        raise NotImplementedError

    @abstractmethod
    def extract_metrics_batch(self, payloads: list[dict]) -> ExtractedBatchResponse:
        """Extrai métricas estruturadas de vários documentos em uma chamada."""
        raise NotImplementedError


class OllamaLLMClient(BaseLLMClient):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: int,
        classification_model: str | None = None,
    ):
        """Inicializa o cliente Ollama local sem fazer chamada de rede."""
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.classification_model = classification_model or model
        self.timeout = timeout

    def classify_document(
        self,
        *,
        company: str,
        title: str | None,
        original_url: str,
        document_type: str | None,
        year: int | None,
        quarter: int | None,
        pages_count: int,
        text_chars: int,
        context: str,
    ) -> DocumentClassification:
        """Classifica utilidade do documento usando a API local do Ollama."""
        response = self._chat(
            user_prompt=_build_classification_prompt(
                company=company,
                title=title,
                original_url=original_url,
                document_type=document_type,
                year=year,
                quarter=quarter,
                pages_count=pages_count,
                text_chars=text_chars,
                context=context,
            ),
            schema=DocumentClassification.model_json_schema(),
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
            model=self.classification_model,
        )
        return DocumentClassification.model_validate_json(response)

    def extract_metrics(
        self,
        *,
        company: str,
        original_url: str,
        context: str,
        year: int | None,
        quarter: int | None,
        title: str | None = None,
        document_type: str | None = None,
    ) -> ExtractedMetricBatch:
        """Extrai métricas de um documento usando a API local do Ollama."""
        response = self._chat(
            user_prompt=_build_single_document_prompt(
                company=company,
                original_url=original_url,
                context=context,
                year=year,
                quarter=quarter,
                title=title,
                document_type=document_type,
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
                        title=payload.get("title"),
                        document_type=payload.get("document_type"),
                    ).metrics,
                }
            )
        return ExtractedBatchResponse.model_validate({"documents": docs})

    def _chat(
        self,
        *,
        user_prompt: str,
        schema: dict,
        system_prompt: str = SYSTEM_PROMPT,
        model: str | None = None,
    ) -> str:
        """Envia uma conversa ao Ollama e retorna o conteúdo textual da resposta."""
        payload = {
            "model": model or self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system_prompt},
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
    def __init__(self, api_key: str, model: str, classification_model: str | None = None):
        """Inicializa o cliente OpenAI validando chave e modelo configurados."""
        if not api_key:
            raise ValueError("OPENAI_API_KEY precisa estar configurada para LLM_PROVIDER=openai.")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.classification_model = classification_model or model

    def classify_document(
        self,
        *,
        company: str,
        title: str | None,
        original_url: str,
        document_type: str | None,
        year: int | None,
        quarter: int | None,
        pages_count: int,
        text_chars: int,
        context: str,
    ) -> DocumentClassification:
        """Classifica utilidade do documento usando Structured Outputs."""
        response = self.client.responses.parse(
            model=self.classification_model,
            input=[
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_classification_prompt(
                        company=company,
                        title=title,
                        original_url=original_url,
                        document_type=document_type,
                        year=year,
                        quarter=quarter,
                        pages_count=pages_count,
                        text_chars=text_chars,
                        context=context,
                    ),
                },
            ],
            text_format=DocumentClassification,
            temperature=0,
        )
        if response.output_parsed is None:
            raise ValueError("OpenAI não retornou classificação estruturada.")
        return response.output_parsed

    def extract_metrics(
        self,
        *,
        company: str,
        original_url: str,
        context: str,
        year: int | None,
        quarter: int | None,
        title: str | None = None,
        document_type: str | None = None,
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
                        title=title,
                        document_type=document_type,
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
        return OpenAILLMClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            classification_model=getattr(settings, "openai_classification_model", None),
        )
    if provider == "ollama":
        return OllamaLLMClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.request_timeout_seconds,
            classification_model=getattr(settings, "ollama_classification_model", None),
        )
    raise ValueError("LLM_PROVIDER deve ser 'openai' ou 'ollama'.")


def _build_classification_prompt(
    *,
    company: str,
    title: str | None,
    original_url: str,
    document_type: str | None,
    year: int | None,
    quarter: int | None,
    pages_count: int,
    text_chars: int,
    context: str,
) -> str:
    """Monta o prompt de usuário para classificação de utilidade documental."""
    return f"""
Classifique o documento abaixo antes da extração de métricas.

Empresa: {company}
Título: {title}
URL original: {original_url}
Tipo inferido por regra: {document_type}
Ano inferido por regra: {year}
Trimestre inferido por regra: {quarter}
Páginas do PDF: {pages_count}
Caracteres extraídos do PDF: {text_chars}

Amostra inteligente do conteúdo:
{context}
""".strip()


def _build_single_document_prompt(
    *,
    company: str,
    original_url: str,
    context: str,
    year: int | None,
    quarter: int | None,
    title: str | None = None,
    document_type: str | None = None,
) -> str:
    """Monta o prompt de usuário para um único documento."""
    return f"""
Extraia as métricas do documento abaixo.

Empresa: {company}
Título: {title}
Tipo inferido: {document_type}
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
Retorne uma entrada em documents para todos os document_ref recebidos, mesmo quando metrics for [].

Documentos:
{json.dumps(payloads, ensure_ascii=False)}
""".strip()
