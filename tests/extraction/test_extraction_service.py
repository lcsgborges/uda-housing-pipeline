from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.extraction.service import ExtractionService, _format_chunk_for_llm, _is_storage_uri
from app.modules.lineage.models import DataLineage
from app.modules.metrics.models import Metric
from app.modules.metrics.schemas import ExtractedBatchResponse


class _FakeParser:
    def __init__(self, pages_text=None):
        self.pages_text = pages_text or ["Vendas liquidas R$ 100 milhoes"]
        self.parsed_paths = []
        self.parsed_bytes = []

    def parse(self, path):
        self.parsed_paths.append(path)
        return SimpleNamespace(pages_text=self.pages_text)

    def parse_bytes(self, content):
        self.parsed_bytes.append(content)
        return SimpleNamespace(pages_text=self.pages_text)


class _FakeStorage:
    def read(self, uri):
        return b"%PDF fake"


class _BatchLLM:
    def __init__(self, returned_refs=None, fail=False):
        self.returned_refs = returned_refs
        self.fail = fail
        self.payloads = []

    def extract_metrics_batch(self, payloads):
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
                        "metrics": [
                            {
                                "company": "MRV",
                                "period_year": 2025,
                                "period_quarter": 3,
                                "metric_name": "vendas_liquidas",
                                "metric_category": "operacional",
                                "value": 100.0,
                                "unit": "R$",
                                "currency": "BRL",
                                "source_page": 1,
                                "source_excerpt": "Vendas liquidas R$ 100 milhoes",
                                "confidence": 0.95,
                            }
                        ],
                    }
                    for ref in refs
                ]
            }
        )


async def _create_company_and_document(db_session, *, status=DocumentStatus.downloaded):
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
        collected_at=datetime.utcnow(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return company, document


@pytest.mark.asyncio
async def test_process_document_persiste_metricas_e_linhagem(db_session):
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
async def test_process_pending_documents_batch_sem_documentos(db_session):
    service = ExtractionService(db_session)

    assert await service.process_pending_documents_batch() == {
        "selected": 0,
        "processed": 0,
        "failed": 0,
    }


@pytest.mark.asyncio
async def test_process_pending_documents_batch_marca_nao_retornado_como_failed(db_session):
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
        status=DocumentStatus.downloaded,
        collected_at=datetime.utcnow(),
    )
    db_session.add(second)
    await db_session.commit()
    await db_session.refresh(second)

    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _BatchLLM(returned_refs=[str(first.id)])

    result = await service.process_pending_documents_batch(batch_size=10)
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert result == {"selected": 2, "processed": 1, "failed": 1}
    assert first.status == DocumentStatus.processed
    assert second.status == DocumentStatus.failed
    assert second.error_message == "Documento não retornado no batch da LLM."


@pytest.mark.asyncio
async def test_process_pending_documents_batch_marca_failed_quando_llm_falha(db_session):
    _, document = await _create_company_and_document(db_session)
    service = ExtractionService(db_session)
    service.parser = _FakeParser()
    service.llm = _BatchLLM(fail=True)

    with pytest.raises(RuntimeError):
        await service.process_pending_documents_batch(batch_size=1)

    await db_session.refresh(document)
    assert document.status == DocumentStatus.failed
    assert document.error_message == "falha llm"


def test_build_context_full_scan_e_chunking(monkeypatch):
    service = ExtractionService(None)
    full_scan = service._build_context(["Texto curto"])

    monkeypatch.setattr(service.settings, "extraction_full_scan_max_chars", 20)
    monkeypatch.setattr(service.settings, "extraction_context_max_chars", 300)
    chunked = service._build_context(
        [
            "DESEMPENHO OPERACIONAL\n"
            + "\n".join(["Vendas liquidas R$ 100 milhoes"] * 30)
        ]
    )

    assert full_scan.startswith("[MODO full_scan]")
    assert chunked.startswith("[MODO semantic_chunking]")
    assert "Página 1" in chunked


def test_parse_document_lida_com_path_storage_uri_e_sem_path():
    service = ExtractionService(None)
    service.parser = _FakeParser()
    service.storage = _FakeStorage()

    path_doc = SimpleNamespace(local_path="/tmp/doc.pdf")
    storage_doc = SimpleNamespace(local_path="s3://bucket/doc.pdf")
    missing_doc = SimpleNamespace(local_path=None)

    assert service._parse_document(path_doc).pages_text
    assert service._parse_document(storage_doc).pages_text
    assert service.parser.parsed_paths == ["/tmp/doc.pdf"]
    assert service.parser.parsed_bytes == [b"%PDF fake"]
    with pytest.raises(ValueError):
        service._parse_document(missing_doc)


def test_format_chunk_e_storage_uri_helpers():
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
