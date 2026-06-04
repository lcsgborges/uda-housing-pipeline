from types import SimpleNamespace

import pytest

from app.modules.extraction import llm_client
from app.modules.extraction.llm_client import (
    BaseLLMClient,
    FakeLLMClient,
    OpenAILLMClient,
    _build_batch_prompt,
    _build_single_document_prompt,
    build_llm_client,
)
from app.modules.metrics.schemas import ExtractedBatchResponse, ExtractedMetricBatch


def test_fake_llm_client_extrai_metricas_e_batch():
    client = FakeLLMClient()

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

    assert single.metrics[0].metric_name == "vendas_liquidas"
    assert batch.documents[0].document_ref == "doc-1"
    assert batch.documents[0].metrics[0].period_quarter == 3


def test_build_llm_client_default_fake(monkeypatch):
    monkeypatch.setattr(
        llm_client,
        "get_settings",
        lambda: SimpleNamespace(llm_provider="fake"),
    )

    assert isinstance(build_llm_client(), FakeLLMClient)


def test_openai_llm_exige_api_key():
    with pytest.raises(ValueError):
        OpenAILLMClient(api_key="", model="gpt")


def test_base_llm_client_metodos_abstratos_rejeitam_uso_direto():
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
        self.output_parsed = parsed


class _Responses:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        text_format = kwargs["text_format"]
        if text_format is ExtractedMetricBatch:
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
        self.api_key = api_key
        self.responses = _Responses()
        _FakeOpenAI.last_instance = self


def test_openai_llm_usa_structured_outputs(monkeypatch):
    monkeypatch.setattr(llm_client, "OpenAI", _FakeOpenAI)
    client = OpenAILLMClient(api_key="sk-test", model="gpt-test")

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
    assert single.metrics[0].metric_name == "vendas_liquidas"
    assert batch.documents[0].document_ref == "doc-1"
    assert calls[0]["text_format"] is ExtractedMetricBatch
    assert calls[1]["text_format"] is ExtractedBatchResponse
    assert calls[0]["temperature"] == 0


def test_openai_llm_rejeita_resposta_sem_payload(monkeypatch):
    class EmptyResponses:
        def parse(self, **kwargs):
            return _ParsedResponse(None)

    class EmptyOpenAI:
        def __init__(self, api_key):
            self.responses = EmptyResponses()

    monkeypatch.setattr(llm_client, "OpenAI", EmptyOpenAI)
    client = OpenAILLMClient(api_key="sk-test", model="gpt-test")

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

    assert "Empresa: MRV" in prompt
    assert "conteudo" in prompt
    assert "vendas_liquidas" in llm_client.SYSTEM_PROMPT
    assert "Catálogo de métricas" in llm_client.SYSTEM_PROMPT
    assert "doc-1" in batch_prompt
