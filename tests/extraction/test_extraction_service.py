import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.extraction import service as extraction_module
from app.modules.extraction.service import (
    ExtractionService,
    _extraction_model_name,
    _format_chunk_for_llm,
    _is_storage_uri,
    _normalize_unit_and_currency,
)
from app.modules.insights.models import DocumentInsight
from app.modules.lineage.models import DataLineage
from app.modules.metrics.models import Metric
from app.modules.metrics.schemas import ExtractedBatchResponse, ExtractedMetricBatch


class _FakeParser:
    def __init__(self, pages_text=None):
        """Inicializa parser fake com páginas e registros de chamadas."""
        self.pages_text = pages_text or ["Vendas liquidas R$ 100 milhoes"]
        self.parsed_paths = []
        self.parsed_bytes = []

    def parse(self, path):
        """Registra parsing por caminho local."""
        self.parsed_paths.append(path)
        return SimpleNamespace(pages_text=self.pages_text)

    def parse_bytes(self, content):
        """Registra parsing por bytes de storage."""
        self.parsed_bytes.append(content)
        return SimpleNamespace(pages_text=self.pages_text)


class _FakeStorage:
    def read(self, uri):
        """Retorna bytes fixos para URIs de storage."""
        return b"%PDF test"


class _BatchLLM:
    def __init__(self, returned_refs=None, fail=False, single_fail=False):
        """Inicializa LLM fake com refs retornadas e falhas opcionais."""
        self.returned_refs = returned_refs
        self.fail = fail
        self.single_fail = single_fail
        self.payloads = []

    def _metric_payload(self):
        """Monta payload de métrica válido para respostas fake."""
        return {
            "company": "MRV",
            "period_year": 2025,
            "period_quarter": 3,
            "period_label": None,
            "metric_name": "vendas_liquidas",
            "metric_category": "operacional",
            "raw_label": None,
            "dimension": None,
            "value": 100.0,
            "unit": "R$",
            "currency": "BRL",
            "source_page": 1,
            "source_excerpt": "Vendas liquidas R$ 100 milhoes",
            "confidence": 0.95,
        }

    def extract_metrics(self, **kwargs):
        """Simula extração individual usada em retry."""
        if self.single_fail:
            raise RuntimeError("falha retry individual")
        return SimpleNamespace(
            metrics=[
                SimpleNamespace(**self._metric_payload()),
            ],
            insights=[],
        )

    def extract_metrics_batch(self, payloads):
        """Simula extração em lote com refs controladas."""
        self.payloads.append(payloads)
        if self.fail:
            raise RuntimeError("falha llm")
        refs = self.returned_refs
        if refs is None:
            refs = [payload["document_ref"] for payload in payloads]
        return ExtractedBatchResponse.model_validate(
            {
                "documents": [
                    {
                        "document_ref": ref,
                        "metrics": [self._metric_payload()],
                    }
                    for ref in refs
                ]
            }
        )


class _EmptyBatchLLM:
    def extract_metrics(self, **kwargs):
        """Retorna extração individual vazia."""
        return SimpleNamespace(metrics=[], insights=[])

    def extract_metrics_batch(self, payloads):
        """Retorna lote sem documentos."""
        return ExtractedBatchResponse.model_validate({"documents": []})


class _EmptyMetricsBatchLLM:
    def extract_metrics(self, **kwargs):
        """Retorna retry individual sem dados."""
        return SimpleNamespace(metrics=[], insights=[])

    def extract_metrics_batch(self, payloads):
        """Retorna documentos do lote sem métricas."""
        return ExtractedBatchResponse.model_validate(
            {
                "documents": [
                    {
                        "document_ref": payload["document_ref"],
                        "metrics": [],
                    }
                    for payload in payloads
                ]
            }
        )


class _AliasMetricLLM:
    def extract_metrics(self, **kwargs):
        """Retorna extração individual vazia para manter foco no batch."""
        return SimpleNamespace(metrics=[], insights=[])

    def extract_metrics_batch(self, payloads):
        """Retorna métrica por alias para validar normalização."""
        return ExtractedBatchResponse.model_validate(
            {
                "documents": [
                    {
                        "document_ref": payloads[0]["document_ref"],
                        "metrics": [
                            {
                                "company": "MRV",
                                "period_year": 2025,
                                "period_quarter": 3,
                                "metric_name": "vendas_contratadas_liquidas",
                                "metric_category": None,
                                "value": 200.0,
                                "unit": "BRL",
                                "currency": "BRL",
                                "source_page": 1,
                                "source_excerpt": "Vendas contratadas líquidas de R$ 200 milhões.",
                                "confidence": 0.88,
                            }
                        ],
                    }
                ]
            }
        )


class _InsightLLM:
    def extract_metrics(self, **kwargs):
        """Retorna extração individual vazia para manter foco no batch."""
        return SimpleNamespace(metrics=[], insights=[])

    def extract_metrics_batch(self, payloads):
        """Retorna métricas e insights para validar persistência mista."""
        return ExtractedBatchResponse.model_validate(
            {
                "documents": [
                    {
                        "document_ref": payloads[0]["document_ref"],
                        "metrics": [
                            {
                                "company": "MRV",
                                "period_year": 2025,
                                "metric_name": "emissoes_gee",
                                "metric_category": "ambiental",
                                "value": None,
                                "unit": "tCO2e",
                                "source_page": 55,
                                "source_excerpt": "Indicador qualitativo sem valor numérico.",
                                "confidence": 0.6,
                            },
                            {
                                "company": "MRV",
                                "period_year": 2025,
                                "period_label": "ano-base 2025",
                                "metric_name": "agua_captada",
                                "metric_category": "ambiental",
                                "raw_label": "Água captada - MRV Brasil",
                                "dimension": "MRV Brasil",
                                "value": 4.96,
                                "unit": "megalitros",
                                "source_page": 67,
                                "source_excerpt": "Água captada totalizou 4,96 megalitros.",
                                "confidence": 0.89,
                            },
                        ],
                        "insights": [
                            {
                                "insight_type": "meta",
                                "topic": "emissoes_gee",
                                "summary": (
                                    "A companhia definiu meta de reduzir emissões "
                                    "por unidade produzida."
                                ),
                                "value_text": "redução de 5% das emissões/UP no ciclo 2025",
                                "period_year": 2025,
                                "source_page": 55,
                                "source_excerpt": (
                                    "meta, para o ciclo de 2025, redução em 5% das emissões."
                                ),
                                "confidence": 0.92,
                            }
                        ],
                    }
                ]
            }
        )


class _SequentialScanLLM:
    def __init__(self):
        """Inicializa LLM fake que retorna uma métrica diferente por parte."""
        self.payloads = []

    def extract_metrics(self, **kwargs):
        """Retorna extração individual vazia para manter foco no batch por parte."""
        return SimpleNamespace(metrics=[], insights=[])

    def extract_metrics_batch(self, payloads):
        """Registra cada payload de parte e retorna métrica rastreável."""
        self.payloads.append(payloads)
        payload = payloads[0]
        part = len(self.payloads)
        return ExtractedBatchResponse.model_validate(
            {
                "documents": [
                    {
                        "document_ref": payload["document_ref"],
                        "metrics": [
                            {
                                "company": "MRV",
                                "period_year": 2025,
                                "period_quarter": 3,
                                "metric_name": "vendas_liquidas",
                                "metric_category": "operacional",
                                "dimension": f"parte {part}",
                                "value": float(part),
                                "unit": "R$",
                                "currency": "BRL",
                                "source_page": part,
                                "source_excerpt": payload["context"][:200],
                                "confidence": 0.9,
                            }
                        ],
                    }
                ]
            }
        )


class _FakeOpenAIBatchClient:
    def __init__(self, output_text: str = ""):
        """Inicializa cliente fake da OpenAI Batch API."""
        self.output_text = output_text
        self.requests = []
        self.batch = SimpleNamespace(
            id="batch_test",
            status="completed",
            output_file_id="file_output",
            error_file_id=None,
        )
        self.uploaded = SimpleNamespace(id="file_input")

    def build_extraction_request(self, *, custom_id: str, payload: dict) -> dict:
        """Monta request fake preservando custom_id e payload."""
        return {"custom_id": custom_id, "payload": payload}

    def submit_requests(self, requests: list[dict]):
        """Registra requests submetidos e retorna arquivo/batch fake."""
        self.requests = requests
        return self.uploaded, self.batch

    def retrieve_batch(self, batch_id: str):
        """Retorna batch fake validando o identificador."""
        assert batch_id == self.batch.id
        return self.batch

    def download_file_text(self, file_id: str) -> str:
        """Retorna output JSONL fake."""
        assert file_id == self.batch.output_file_id
        return self.output_text


async def _create_company_and_document(db_session, *, status=DocumentStatus.classified_useful):
    """Cria empresa e documento para testes do serviço de extração."""
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Prévia Operacional 3T25",
        original_url="https://ri.mrv.com.br/previa-3t25.pdf",
        local_path="/tmp/previa.pdf",
        file_hash="hash_extraction",
        year=2025,
        quarter=3,
        document_type="previa_operacional",
        status=status,
        collected_at=utc_now(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return company, document


@pytest.mark.asyncio
async def test_process_document_persiste_metricas_e_linhagem(db_session):
    """Valida persistência de métrica, linhagem e status processado."""
    company, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _BatchLLM()

    await service.process_document(document, company_name=company.name)

    metrics = list((await db_session.scalars(select(Metric))).all())
    lineage = list((await db_session.scalars(select(DataLineage))).all())
    await db_session.refresh(document)

    assert metrics[0].metric_name == "vendas_liquidas"
    assert lineage[0].original_url == document.original_url
    assert lineage[0].metric_id == metrics[0].id
    assert document.status == DocumentStatus.processed
    assert document.error_message is None


@pytest.mark.asyncio
async def test_process_document_normaliza_alias_e_enriquece_metadados(db_session):
    """Garante normalização de alias e enriquecimento por catálogo."""
    company, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _AliasMetricLLM()

    await service.process_document(document, company_name=company.name)

    metric = (await db_session.scalars(select(Metric))).one()

    assert metric.metric_name == "vendas_liquidas"
    assert metric.metric_category == "operacional"
    assert metric.unit == "R$"
    assert metric.currency == "BRL"


@pytest.mark.asyncio
async def test_process_document_persiste_insights_e_contexto_da_metrica(db_session):
    """Valida persistência de insights e campos contextuais da métrica."""
    company, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _InsightLLM()

    await service.process_document(document, company_name=company.name)

    metrics = list((await db_session.scalars(select(Metric))).all())
    insights = list((await db_session.scalars(select(DocumentInsight))).all())
    await db_session.refresh(document)

    assert len(metrics) == 1
    assert metrics[0].metric_name == "agua_captada"
    assert metrics[0].value == 4.96
    assert metrics[0].raw_label == "Água captada - MRV Brasil"
    assert metrics[0].dimension == "MRV Brasil"
    assert metrics[0].period_label == "ano-base 2025"
    assert len(insights) == 1
    assert insights[0].insight_type == "meta"
    assert insights[0].topic == "emissoes_gee"
    assert document.status == DocumentStatus.processed


@pytest.mark.asyncio
async def test_process_document_varre_documento_longo_em_partes_sequenciais(
    monkeypatch,
    db_session,
):
    """Garante que documentos longos são analisados em várias partes sequenciais."""
    company, document = await _create_company_and_document(db_session)
    pages = [
        "Página inicial com vendas liquidas " + ("A " * 120),
        "Página intermediária com banco de terrenos " + ("B " * 120),
        "Página final com distratos e repasses " + ("C " * 120),
    ]
    service = ExtractionService(db_session)
    service.parser = _FakeParser(pages_text=pages)
    service.llm = _SequentialScanLLM()
    monkeypatch.setattr(service.settings, "extraction_full_scan_max_chars", 20)
    monkeypatch.setattr(service.settings, "extraction_context_max_chars", 180)

    await service.process_document(document, company_name=company.name)

    contexts = [payloads[0]["context"] for payloads in service.llm.payloads]
    metrics = list((await db_session.scalars(select(Metric))).all())
    await db_session.refresh(document)

    assert len(contexts) > 1
    assert contexts[0].startswith("[MODO sequential_scan")
    assert any("[Página 1" in context for context in contexts)
    assert any("[Página 3" in context for context in contexts)
    assert len(metrics) == len(contexts)
    assert document.status == DocumentStatus.processed


@pytest.mark.asyncio
async def test_submit_openai_extraction_batch_cria_jsonl_por_partes(
    monkeypatch,
    db_session,
):
    """Garante submissão de partes documentais pela OpenAI Batch API."""
    _, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser(
        pages_text=[
            "Página inicial com vendas liquidas " + ("A " * 120),
            "Página final com landbank " + ("B " * 120),
        ]
    )
    monkeypatch.setattr(service.settings, "llm_provider", "openai")
    monkeypatch.setattr(service.settings, "extraction_full_scan_max_chars", 20)
    monkeypatch.setattr(service.settings, "extraction_context_max_chars", 180)
    fake_client = _FakeOpenAIBatchClient()
    monkeypatch.setattr(extraction_module, "build_openai_batch_client", lambda: fake_client)

    result = await service.submit_openai_extraction_batch(batch_size=1)
    await db_session.refresh(document)

    assert result["batch_id"] == "batch_test"
    assert result["input_file_id"] == "file_input"
    assert result["requests"] == len(fake_client.requests)
    assert len(fake_client.requests) > 1
    assert fake_client.requests[0]["custom_id"].startswith(f"document-{document.id}-part-1-of-")
    assert fake_client.requests[0]["payload"]["document_ref"].startswith(f"{document.id}:part:1")
    assert document.status == DocumentStatus.processing
    assert document.error_message == "OpenAI batch pendente: batch_test"


@pytest.mark.asyncio
async def test_import_openai_extraction_batch_persiste_resultado(
    monkeypatch,
    db_session,
):
    """Garante importação de output JSONL da OpenAI Batch API."""
    _, document = await _create_company_and_document(db_session, status=DocumentStatus.processing)
    extracted = ExtractedMetricBatch.model_validate(
        {
            "metrics": [
                {
                    "company": "MRV",
                    "period_year": 2025,
                    "period_quarter": 3,
                    "metric_name": "vendas_liquidas",
                    "metric_category": "operacional",
                    "value": 123.0,
                    "unit": "R$",
                    "currency": "BRL",
                    "source_page": 1,
                    "source_excerpt": "Vendas liquidas de R$ 123 milhões.",
                    "confidence": 0.91,
                }
            ],
            "insights": [],
        }
    )
    output_line = {
        "custom_id": f"document-{document.id}-part-1-of-1",
        "response": {
            "status_code": 200,
            "body": {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": extracted.model_dump_json(),
                            }
                        ]
                    }
                ]
            },
        },
        "error": None,
    }
    fake_client = _FakeOpenAIBatchClient(
        output_text=json.dumps(output_line, ensure_ascii=False) + "\n"
    )
    monkeypatch.setattr(extraction_module, "build_openai_batch_client", lambda: fake_client)
    service = ExtractionService(db_session)
    monkeypatch.setattr(service.settings, "llm_provider", "openai")

    result = await service.import_openai_extraction_batch("batch_test")

    metric = (await db_session.scalars(select(Metric))).one()
    await db_session.refresh(document)

    assert result["imported"] == 1
    assert result["failed"] == 0
    assert metric.metric_name == "vendas_liquidas"
    assert metric.value == 123.0
    assert document.status == DocumentStatus.processed


@pytest.mark.asyncio
async def test_process_document_rejeita_extracao_sem_metricas(db_session):
    """Garante falha quando extração não retorna métricas nem insights."""
    company, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _EmptyBatchLLM()

    with pytest.raises(ValueError, match="Nenhuma métrica"):
        await service.process_document(document, company_name=company.name)
    await db_session.refresh(document)

    assert document.status == DocumentStatus.failed
    assert document.error_message == "Nenhuma métrica ou insight extraído do documento."


@pytest.mark.asyncio
async def test_process_pending_documents_batch_sem_documentos(db_session):
    """Valida retorno vazio quando não há documentos úteis pendentes."""
    service = ExtractionService(db_session)

    assert await service.process_pending_documents_batch() == {
        "selected": 0,
        "processed": 0,
        "failed": 0,
    }


@pytest.mark.asyncio
async def test_process_all_pending_documents_agrega_lotes(db_session, monkeypatch):
    """Garante agregação de totais ao processar todos os lotes pendentes."""
    service = ExtractionService(db_session)
    results = [
        {"selected": 2, "processed": 2, "failed": 0},
        {"selected": 1, "processed": 0, "failed": 1},
        {"selected": 0, "processed": 0, "failed": 0},
    ]

    async def fake_process_pending_documents_batch(batch_size=None):
        """Retorna lotes fake em sequência para testar agregação."""
        assert batch_size == 3
        return results.pop(0)

    monkeypatch.setattr(
        service,
        "process_pending_documents_batch",
        fake_process_pending_documents_batch,
    )

    assert await service.process_all_pending_documents(batch_size=3) == {
        "batches": 2,
        "selected": 3,
        "processed": 2,
        "failed": 1,
    }


@pytest.mark.asyncio
async def test_process_pending_documents_batch_reprocessa_doc_nao_retornado(db_session):
    """Garante retry individual para documento ausente na resposta batch."""
    company, first = await _create_company_and_document(db_session)
    second = Document(
        company_id=company.id,
        title="Resultado 3T25",
        original_url="https://ri.mrv.com.br/resultado-3t25.pdf",
        local_path="/tmp/resultado.pdf",
        file_hash="hash_extraction_2",
        year=2025,
        quarter=3,
        document_type="resultado_trimestral",
        status=DocumentStatus.classified_useful,
        collected_at=utc_now(),
    )
    db_session.add(second)
    await db_session.commit()
    await db_session.refresh(second)

    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _BatchLLM(returned_refs=["unknown-document", str(first.id)])

    result = await service.process_pending_documents_batch(batch_size=10)
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert result == {"selected": 2, "processed": 2, "failed": 0}
    assert first.status == DocumentStatus.processed
    assert second.status == DocumentStatus.processed
    assert second.error_message is None


@pytest.mark.asyncio
async def test_process_pending_documents_batch_marca_nao_retornado_failed_se_retry_falha(
    db_session,
):
    """Garante falha quando documento ausente no batch também falha no retry."""
    company, first = await _create_company_and_document(db_session)
    second = Document(
        company_id=company.id,
        title="Resultado 3T25",
        original_url="https://ri.mrv.com.br/resultado-3t25.pdf",
        local_path="/tmp/resultado.pdf",
        file_hash="hash_extraction_2",
        year=2025,
        quarter=3,
        document_type="resultado_trimestral",
        status=DocumentStatus.classified_useful,
        collected_at=utc_now(),
    )
    db_session.add(second)
    await db_session.commit()
    await db_session.refresh(second)

    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _BatchLLM(returned_refs=[str(first.id)], single_fail=True)

    result = await service.process_pending_documents_batch(batch_size=10)
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert result == {"selected": 2, "processed": 1, "failed": 1}
    assert first.status == DocumentStatus.processed
    assert second.status == DocumentStatus.failed
    assert second.error_message.startswith("Documento não retornado no batch da LLM.")


@pytest.mark.asyncio
async def test_process_pending_documents_batch_marca_failed_quando_sem_metricas(db_session):
    """Garante status failed quando lote retorna documento sem dados."""
    _, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _EmptyMetricsBatchLLM()

    result = await service.process_pending_documents_batch(batch_size=1)
    await db_session.refresh(document)
    metrics = list((await db_session.scalars(select(Metric))).all())

    assert result == {"selected": 1, "processed": 0, "failed": 1}
    assert metrics == []
    assert document.status == DocumentStatus.failed
    assert document.error_message == "Nenhuma métrica ou insight extraído do documento."


@pytest.mark.asyncio
async def test_process_pending_documents_batch_marca_failed_quando_llm_falha(db_session):
    """Garante status failed quando a chamada batch da LLM falha."""
    _, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _BatchLLM(fail=True)

    result = await service.process_pending_documents_batch(batch_size=1)
    await db_session.refresh(document)

    assert result == {"selected": 1, "processed": 0, "failed": 1}
    assert document.status == DocumentStatus.failed
    assert document.error_message == "falha llm"


def test_build_context_full_scan_e_varredura_sequencial(monkeypatch):
    """Valida escolha entre contexto completo e varredura sequencial."""
    service = ExtractionService(None)
    full_scan = service._build_context(["Texto curto"])

    monkeypatch.setattr(service.settings, "extraction_full_scan_max_chars", 20)
    monkeypatch.setattr(service.settings, "extraction_context_max_chars", 160)
    long_pages = [
        "DESEMPENHO OPERACIONAL\n" + ("Vendas liquidas R$ 100 milhoes. " * 8),
        "BANCO DE TERRENOS\n" + ("Landbank total de R$ 200 milhoes. " * 8),
    ]
    contexts = service._build_contexts(long_pages)
    first_context = service._build_context(long_pages)

    assert full_scan.startswith("[MODO full_scan]")
    assert len(contexts) > 1
    assert first_context == contexts[0]
    assert all(context.startswith("[MODO sequential_scan") for context in contexts)
    assert any("Página 2" in context for context in contexts)


def test_parse_document_lida_com_path_storage_uri_e_sem_path():
    """Cobre parsing por path local, storage URI e ausência de caminho."""
    service = ExtractionService(None)
    service.parser = _FakeParser()
    service.storage = _FakeStorage()

    path_doc = SimpleNamespace(local_path="/tmp/doc.pdf")
    storage_doc = SimpleNamespace(local_path="s3://bucket/doc.pdf")
    missing_doc = SimpleNamespace(local_path=None)

    assert service._parse_document(path_doc).pages_text
    assert service._parse_document(storage_doc).pages_text
    assert service.parser.parsed_paths == ["/tmp/doc.pdf"]
    assert service.parser.parsed_bytes == [b"%PDF test"]
    with pytest.raises(ValueError):
        service._parse_document(missing_doc)


def test_format_chunk_e_storage_uri_helpers():
    """Valida formatação de chunk e detecção de URI de storage."""
    chunk = SimpleNamespace(
        page=2,
        ordinal=4,
        score=9,
        heading="DESEMPENHO OPERACIONAL",
        tags=("operacional", "tabela"),
        text="Vendas liquidas",
    )

    formatted = _format_chunk_for_llm(chunk)

    assert _is_storage_uri("file:///tmp/doc.pdf") is True
    assert _is_storage_uri("/tmp/doc.pdf") is False
    assert "Título/seção: DESEMPENHO OPERACIONAL" in formatted
    assert "Tags semânticas: operacional, tabela" in formatted


def test_normalize_unit_and_currency_aplica_defaults_quando_sem_moeda():
    """Garante aplicação de defaults de unidade e moeda."""
    unit, currency = _normalize_unit_and_currency(
        unit=None,
        currency=None,
        default_unit="R$",
        default_currency="BRL",
    )
    percent_unit, percent_currency = _normalize_unit_and_currency(
        unit="%",
        currency=None,
        default_unit="%",
        default_currency=None,
    )

    assert (unit, currency) == ("R$", "BRL")
    assert (percent_unit, percent_currency) == ("%", None)


def test_extraction_model_name_resolve_provider():
    """Valida resolução do nome de modelo usado na linhagem."""
    assert (
        _extraction_model_name(
            SimpleNamespace(llm_provider="openai", openai_model="gpt", ollama_model="llama")
        )
        == "gpt"
    )
    assert (
        _extraction_model_name(
            SimpleNamespace(llm_provider="ollama", openai_model="gpt", ollama_model="llama")
        )
        == "llama"
    )
    assert (
        _extraction_model_name(
            SimpleNamespace(llm_provider="custom", openai_model="gpt", ollama_model="llama")
        )
        == "custom"
    )
