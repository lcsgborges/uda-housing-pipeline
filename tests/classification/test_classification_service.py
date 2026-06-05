from types import SimpleNamespace

import pytest

from app.core.time import utc_now
from app.modules.classification.schemas import DocumentClassification
from app.modules.classification.service import ClassificationService
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus


class _FakeParser:
    def __init__(self, pages_text=None):
        """Inicializa parser fake com páginas textuais controladas."""
        self.pages_text = pages_text or [
            "MRV divulga receita líquida de R$ 100 milhões e emissões de 10 tCO2e."
        ]

    def parse(self, path):
        """Simula parsing de arquivo local."""
        return self._parsed()

    def parse_bytes(self, content):
        """Simula parsing de bytes lidos do storage."""
        return self._parsed()

    def _parsed(self):
        """Monta objeto parseado compatível com o serviço."""
        return SimpleNamespace(
            pages_text=self.pages_text,
            full_text="\n\n".join(self.pages_text),
            pages_count=len(self.pages_text),
        )


class _FakeLLM:
    def __init__(self, classification):
        """Inicializa cliente LLM fake com classificação fixa."""
        self.classification = classification
        self.calls = []

    def classify_document(self, **kwargs):
        """Registra argumentos e devolve a classificação configurada."""
        self.calls.append(kwargs)
        return self.classification


async def _create_company_and_document(db_session, *, title="Resultado 1T26"):
    """Cria empresa e documento baixado para testes de classificação."""
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title=title,
        original_url="https://ri.mrv.com.br/doc.pdf",
        local_path="/tmp/doc.pdf",
        file_hash="hash_classification",
        year=None,
        quarter=None,
        document_type="outro",
        status=DocumentStatus.downloaded,
        collected_at=utc_now(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return company, document


@pytest.mark.asyncio
async def test_classifica_documento_util_e_persiste_metadados(db_session):
    """Valida classificação útil e persistência dos metadados no documento."""
    company, document = await _create_company_and_document(db_session)
    classification = DocumentClassification(
        is_useful=True,
        document_type="resultado_trimestral",
        domains=["financeiro", "operacional"],
        year=2026,
        quarter=1,
        extraction_strategy="semantic_chunking",
        reason="Contém métricas financeiras e operacionais.",
        confidence=0.91,
    )
    service = ClassificationService(db_session)
    service.parser = _FakeParser()
    service.llm = _FakeLLM(classification)

    result = await service.classify_document(document, company_name=company.name)
    await db_session.refresh(document)

    assert result == classification
    assert document.status == DocumentStatus.classified_useful
    assert document.classification_is_useful is True
    assert document.classification_confidence == 0.91
    assert document.classification_reason == "Contém métricas financeiras e operacionais."
    assert document.detected_domains == ["financeiro", "operacional"]
    assert document.extraction_strategy == "semantic_chunking"
    assert document.document_type == "resultado_trimestral"
    assert document.year == 2026
    assert document.quarter == 1
    assert document.classified_at is not None
    assert service.llm.calls[0]["pages_count"] == 1


@pytest.mark.asyncio
async def test_classifica_documento_irrelevante_como_ignored(db_session):
    """Garante que documento irrelevante recebe status ignored_not_relevant."""
    company, document = await _create_company_and_document(db_session, title="Comunicado")
    classification = DocumentClassification(
        is_useful=False,
        document_type="comunicado",
        domains=[],
        year=None,
        quarter=None,
        extraction_strategy="ignore",
        reason="Comunicado sem métricas quantitativas.",
        confidence=0.87,
    )
    service = ClassificationService(db_session)
    service.parser = _FakeParser(
        [
            "Texto institucional sobre mudança de endereço e comunicação ao mercado, "
            "sem indicadores quantitativos ou tabelas financeiras."
        ]
    )
    service.llm = _FakeLLM(classification)

    await service.classify_document(document, company_name=company.name)
    await db_session.refresh(document)

    assert document.status == DocumentStatus.ignored_not_relevant
    assert document.error_message == "Comunicado sem métricas quantitativas."
    assert document.classification_is_useful is False


@pytest.mark.asyncio
async def test_classificacao_detecta_pdf_sem_texto_como_needs_ocr(db_session):
    """Garante detecção determinística de PDF sem texto extraível."""
    company, document = await _create_company_and_document(db_session)
    service = ClassificationService(db_session)
    service.parser = _FakeParser(["", "", ""])
    service.llm = _FakeLLM(
        DocumentClassification(
            is_useful=True,
            document_type="resultado_trimestral",
            domains=["financeiro"],
            extraction_strategy="full_scan",
            reason="Não deve ser chamado.",
            confidence=0.5,
        )
    )

    await service.classify_document(document, company_name=company.name)
    await db_session.refresh(document)

    assert service.llm.calls == []
    assert document.status == DocumentStatus.needs_ocr
    assert document.extraction_strategy == "needs_ocr"
    assert document.classification_confidence == 0.95


@pytest.mark.asyncio
async def test_process_pending_documents_batch_contabiliza_resultados(db_session):
    """Valida contadores do lote de classificação de documentos pendentes."""
    company, first = await _create_company_and_document(db_session)
    second = Document(
        company_id=company.id,
        title="Comunicado",
        original_url="https://ri.mrv.com.br/comunicado.pdf",
        local_path="/tmp/comunicado.pdf",
        file_hash="hash_classification_2",
        document_type="outro",
        status=DocumentStatus.downloaded,
        collected_at=utc_now(),
    )
    db_session.add(second)
    await db_session.commit()
    await db_session.refresh(second)

    useful = DocumentClassification(
        is_useful=True,
        document_type="resultado_trimestral",
        domains=["financeiro"],
        year=2026,
        quarter=1,
        extraction_strategy="full_scan",
        reason="Contém métricas.",
        confidence=0.9,
    )
    service = ClassificationService(db_session)
    service.parser = _FakeParser()
    service.llm = _FakeLLM(useful)

    result = await service.process_pending_documents_batch(batch_size=10)
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert result == {"selected": 2, "useful": 2, "ignored": 0, "needs_ocr": 0, "failed": 0}
    assert first.status == DocumentStatus.classified_useful
    assert second.status == DocumentStatus.classified_useful
