from types import SimpleNamespace

import pytest

from app.modules.extraction import llm_client
from app.modules.extraction.llm_client import (
    BaseLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
    _build_batch_prompt,
    _build_classification_prompt,
    _build_single_document_prompt,
    build_llm_client,
)
from app.modules.metrics.schemas import ExtractedBatchResponse, ExtractedMetricBatch


class _HTTPResponse:
    def __init__(self, payload, status_error=False):
        """Inicializa resposta HTTP fake com payload e erro opcional."""
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        """Simula erro HTTP quando configurado."""
        if self.status_error:
            raise RuntimeError("erro http")

    def json(self):
        """Retorna o payload JSON fake."""
        return self.payload


class _HTTPClient:
    last_instance = None
    instances = []

    def __init__(self, timeout):
        """Inicializa cliente HTTP fake registrando timeout e requisições."""
        self.timeout = timeout
        self.requests = []
        _HTTPClient.instances.append(self)
        _HTTPClient.last_instance = self

    def __enter__(self):
        """Entra no contexto do cliente HTTP fake."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Sai do contexto sem suprimir exceções."""
        return None

    def post(self, url, json):
        """Simula POST do Ollama retornando contratos estruturados."""
        self.requests.append((url, json))
        if json["format"]["title"] == "DocumentClassification":
            content = llm_client.DocumentClassification.model_validate(
                {
                    "is_useful": True,
                    "document_type": "resultado_trimestral",
                    "domains": ["financeiro"],
                    "year": 2025,
                    "quarter": 3,
                    "extraction_strategy": "full_scan",
                    "reason": "Contém métricas financeiras.",
                    "confidence": 0.9,
                }
            ).model_dump_json()
        elif json["format"]["title"] == "ExtractedMetricBatch":
            content = ExtractedMetricBatch.model_validate(
                {
                    "metrics": [
                        {
                            "company": "MRV",
                            "period_year": 2025,
                            "period_quarter": 3,
                            "metric_name": "vendas_liquidas",
                            "confidence": 0.9,
                        }
                    ]
                }
            ).model_dump_json()
        else:
            content = "{}"
        return _HTTPResponse({"message": {"content": content}})


def test_ollama_llm_client_extrai_metricas_e_batch(monkeypatch):
    """Valida classificação, extração e lote usando cliente Ollama fake."""
    _HTTPClient.instances = []
    monkeypatch.setattr(llm_client.httpx, "Client", _HTTPClient)
    client = OllamaLLMClient(
        base_url="http://ollama:11434",
        model="llama3.1",
        classification_model="llama-small",
        timeout=30,
    )

    classification = client.classify_document(
        company="MRV",
        title="Resultado 3T25",
        original_url="https://example.com/doc.pdf",
        document_type="resultado_trimestral",
        year=2025,
        quarter=3,
        pages_count=10,
        text_chars=1000,
        context="texto",
    )
    single = client.extract_metrics(
        company="MRV",
        original_url="https://example.com/doc.pdf",
        context="texto",
        year=2025,
        quarter=3,
    )
    batch = client.extract_metrics_batch(
        [
            {
                "document_ref": "doc-1",
                "company": "MRV",
                "original_url": "https://example.com/doc.pdf",
                "context": "texto",
                "year": 2025,
                "quarter": 3,
            }
        ]
    )

    assert classification.is_useful is True
    assert single.metrics[0].metric_name == "vendas_liquidas"
    assert batch.documents[0].document_ref == "doc-1"
    assert batch.documents[0].metrics[0].period_quarter == 3
    assert _HTTPClient.last_instance.timeout == 30
    assert _HTTPClient.instances[0].requests[0][0] == "http://ollama:11434/api/chat"
    assert _HTTPClient.instances[0].requests[0][1]["stream"] is False
    assert _HTTPClient.instances[0].requests[0][1]["model"] == "llama-small"


def test_ollama_llm_rejeita_resposta_sem_conteudo(monkeypatch):
    """Garante erro quando Ollama não retorna conteúdo."""
    class EmptyHTTPClient(_HTTPClient):
        def post(self, url, json):
            """Retorna mensagem vazia para acionar validação de conteúdo."""
            return _HTTPResponse({"message": {}})

    monkeypatch.setattr(llm_client.httpx, "Client", EmptyHTTPClient)
    client = OllamaLLMClient(base_url="http://ollama:11434", model="llama3.1", timeout=30)

    with pytest.raises(ValueError):
        client.extract_metrics(
            company="MRV",
            original_url="https://example.com/doc.pdf",
            context="texto",
            year=2025,
            quarter=3,
        )


def test_build_llm_client_default_ollama(monkeypatch):
    """Valida construção padrão do cliente Ollama por settings."""
    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(
            llm_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_model="llama3.1",
            ollama_classification_model="llama-small",
            request_timeout_seconds=20,
        ),
    )

    assert isinstance(build_llm_client(), OllamaLLMClient)


def test_build_llm_client_openai(monkeypatch):
    """Valida construção do cliente OpenAI por settings."""
    sentinel = object()

    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(
            llm_provider="openai",
            openai_api_key="sk-test",
            openai_model="gpt-test",
        ),
    )
    monkeypatch.setattr(
        llm_client,
        "OpenAILLMClient",
        lambda api_key, model, classification_model=None: sentinel,
    )

    assert build_llm_client() is sentinel


def test_build_llm_client_rejeita_provider_desconhecido(monkeypatch):
    """Garante rejeição de provider de LLM desconhecido."""
    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(llm_provider="anthropic"),
    )

    with pytest.raises(ValueError):
        build_llm_client()


def test_openai_llm_exige_api_key():
    """Garante que cliente OpenAI exige API key."""
    with pytest.raises(ValueError):
        OpenAILLMClient(api_key="", model="gpt")


def test_base_llm_client_metodos_abstratos_rejeitam_uso_direto():
    """Cobre métodos abstratos da interface base."""
    with pytest.raises(NotImplementedError):
        BaseLLMClient.classify_document(
            object(),
            company="MRV",
            title="Resultado",
            original_url="https://example.com/doc.pdf",
            document_type="resultado_trimestral",
            year=2025,
            quarter=3,
            pages_count=10,
            text_chars=1000,
            context="texto",
        )

    with pytest.raises(NotImplementedError):
        BaseLLMClient.extract_metrics(
            object(),
            company="MRV",
            original_url="https://example.com/doc.pdf",
            context="texto",
            year=2025,
            quarter=3,
        )

    with pytest.raises(NotImplementedError):
        BaseLLMClient.extract_metrics_batch(object(), [])


class _ParsedResponse:
    def __init__(self, parsed):
        """Inicializa resposta parseada fake."""
        self.output_parsed = parsed


class _Responses:
    def __init__(self):
        """Inicializa agregador fake de chamadas Responses API."""
        self.calls = []

    def parse(self, **kwargs):
        """Simula Responses API devolvendo o modelo Pydantic solicitado."""
        self.calls.append(kwargs)
        text_format = kwargs["text_format"]
        if text_format is llm_client.DocumentClassification:
            parsed = llm_client.DocumentClassification.model_validate(
                {
                    "is_useful": True,
                    "document_type": "resultado_trimestral",
                    "domains": ["financeiro"],
                    "year": 2025,
                    "quarter": 3,
                    "extraction_strategy": "full_scan",
                    "reason": "Contém métricas financeiras.",
                    "confidence": 0.9,
                }
            )
        elif text_format is ExtractedMetricBatch:
            parsed = ExtractedMetricBatch.model_validate(
                {
                    "metrics": [
                        {
                            "company": "MRV",
                            "metric_name": "vendas_liquidas",
                            "confidence": 0.9,
                        }
                    ]
                }
            )
        else:
            parsed = ExtractedBatchResponse.model_validate(
                {
                    "documents": [
                        {
                            "document_ref": "doc-1",
                            "metrics": [
                                {
                                    "company": "MRV",
                                    "metric_name": "vendas_liquidas",
                                    "confidence": 0.9,
                                }
                            ],
                        }
                    ]
                }
            )
        return _ParsedResponse(parsed)


class _FakeOpenAI:
    last_instance = None

    def __init__(self, api_key):
        """Inicializa cliente OpenAI fake e registra última instância."""
        self.api_key = api_key
        self.responses = _Responses()
        _FakeOpenAI.last_instance = self


def test_openai_llm_usa_structured_outputs(monkeypatch):
    """Valida uso de Structured Outputs para classificação, single e batch."""
    monkeypatch.setattr(llm_client, "OpenAI", _FakeOpenAI)
    client = OpenAILLMClient(
        api_key="sk-test",
        model="gpt-test",
        classification_model="gpt-cheap",
    )

    classification = client.classify_document(
        company="MRV",
        title="Resultado 3T25",
        original_url="https://example.com/doc.pdf",
        document_type="resultado_trimestral",
        year=2025,
        quarter=3,
        pages_count=10,
        text_chars=1000,
        context="conteudo",
    )
    single = client.extract_metrics(
        company="MRV",
        original_url="https://example.com/doc.pdf",
        context="conteudo",
        year=2025,
        quarter=3,
    )
    batch = client.extract_metrics_batch(
        [
            {
                "document_ref": "doc-1",
                "company": "MRV",
                "original_url": "https://example.com/doc.pdf",
                "context": "conteudo",
                "year": 2025,
                "quarter": 3,
            }
        ]
    )

    calls = _FakeOpenAI.last_instance.responses.calls
    assert classification.document_type == "resultado_trimestral"
    assert single.metrics[0].metric_name == "vendas_liquidas"
    assert batch.documents[0].document_ref == "doc-1"
    assert calls[0]["model"] == "gpt-cheap"
    assert calls[0]["text_format"] is llm_client.DocumentClassification
    assert calls[1]["text_format"] is ExtractedMetricBatch
    assert calls[2]["text_format"] is ExtractedBatchResponse
    assert calls[0]["temperature"] == 0


def test_openai_llm_rejeita_resposta_sem_payload(monkeypatch):
    """Garante erro quando OpenAI não retorna payload parseado."""
    class EmptyResponses:
        def parse(self, **kwargs):
            """Retorna resposta sem objeto parseado."""
            return _ParsedResponse(None)

    class EmptyOpenAI:
        def __init__(self, api_key):
            """Inicializa cliente fake com Responses API vazia."""
            self.responses = EmptyResponses()

    monkeypatch.setattr(llm_client, "OpenAI", EmptyOpenAI)
    client = OpenAILLMClient(api_key="sk-test", model="gpt-test")

    with pytest.raises(ValueError):
        client.classify_document(
            company="MRV",
            title="Resultado",
            original_url="https://example.com/doc.pdf",
            document_type="resultado_trimestral",
            year=2025,
            quarter=3,
            pages_count=10,
            text_chars=1000,
            context="conteudo",
        )

    with pytest.raises(ValueError):
        client.extract_metrics(
            company="MRV",
            original_url="https://example.com/doc.pdf",
            context="conteudo",
            year=2025,
            quarter=3,
        )

    with pytest.raises(ValueError):
        client.extract_metrics_batch([])


def test_prompt_builders_incluem_contexto_e_document_ref():
    """Valida que prompts incluem contexto, catálogo e document_ref."""
    classification_prompt = _build_classification_prompt(
        company="MRV",
        title="Resultado",
        original_url="https://example.com/doc.pdf",
        document_type="resultado_trimestral",
        year=2025,
        quarter=3,
        pages_count=10,
        text_chars=1000,
        context="amostra",
    )
    prompt = _build_single_document_prompt(
        company="MRV",
        original_url="https://example.com/doc.pdf",
        context="conteudo",
        year=2025,
        quarter=3,
    )
    batch_prompt = _build_batch_prompt(
        [
            {
                "document_ref": "doc-1",
                "company": "MRV",
                "original_url": "url",
                "context": "ctx",
                "year": 2025,
                "quarter": 3,
            }
        ]
    )

    assert "Classifique o documento" in classification_prompt
    assert "amostra" in classification_prompt
    assert "Empresa: MRV" in prompt
    assert "conteudo" in prompt
    assert "vendas_liquidas" in llm_client.SYSTEM_PROMPT
    assert "Catálogo de métricas" in llm_client.SYSTEM_PROMPT
    assert "doc-1" in batch_prompt
