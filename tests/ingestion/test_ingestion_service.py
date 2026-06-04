from datetime import datetime

import pytest

from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.ingestion import service as ingestion_module
from app.modules.ingestion.service import IngestionService, infer_document_type, infer_period
from app.modules.storage.service import StoredObject


class _FakeDownloader:
    def __init__(self, content: bytes):
        self.content = content
        self.urls = []

    def download(self, url, destination_dir):
        self.urls.append((url, destination_dir))
        return self.content


class _FakeStorage:
    def __init__(self):
        self.stored = []

    def store(self, *, key: str, content: bytes):
        self.stored.append((key, content))
        return StoredObject(uri=f"file:///{key}", size_bytes=len(content))


class _FakeExtraction:
    def __init__(self):
        self.documents = []

    async def process_document(self, document, company_name):
        self.documents.append((document, company_name))


@pytest.mark.parametrize(
    ("url", "title", "expected"),
    [
        ("https://ri.com/previa-3t25.pdf", "", (2025, 3)),
        ("https://ri.com/doc.pdf", "Resultado 4T2026", (2026, 4)),
        ("https://ri.com/doc.pdf", "Sem período", (None, None)),
    ],
)
def test_infer_period(url, title, expected):
    assert infer_period(url=url, title=title) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Prévia Operacional", "previa_operacional"),
        ("Previa Operacional", "previa_operacional"),
        ("Resultado Trimestral", "resultado_trimestral"),
        ("Comunicado ao mercado", "outro"),
    ],
)
def test_infer_document_type(text, expected):
    assert infer_document_type(text) == expected


@pytest.mark.asyncio
async def test_ingestion_run_processa_links_de_empresas_ativas(monkeypatch, db_session):
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br", is_active=True)
    inactive = Company(
        name="Inativa",
        ticker="INAT3",
        ri_url="https://ri.inativa.com.br",
        is_active=False,
    )
    db_session.add_all([company, inactive])
    await db_session.commit()

    service = IngestionService(db_session)
    service.scraper = type(
        "Scraper",
        (),
        {"find_pdf_links": lambda self, url: [{"url": f"{url}/doc.pdf", "title": "Prévia"}]},
    )()

    async def fake_ingest(company, url, title, extract_after_ingestion=True):
        assert company.ticker == "MRVE3"
        assert extract_after_ingestion is True
        return "processed"

    monkeypatch.setattr(service, "_ingest_link", fake_ingest)

    result = await service.run()

    assert result == {
        "companies": 1,
        "discovered": 1,
        "processed": 1,
        "ignored_duplicates": 0,
    }


@pytest.mark.asyncio
async def test_ingest_link_novo_documento_salva_e_extrai(db_session):
    company = Company(name="Direcional", ticker="DIRR3", ri_url="https://ri.direcional.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    service = IngestionService(db_session)
    service.downloader = _FakeDownloader(b"pdf novo")
    service.storage = _FakeStorage()
    service.extraction_service = _FakeExtraction()

    outcome = await service._ingest_link(
        company,
        "https://ri.direcional.com.br/previa-2t25.pdf",
        "Prévia Operacional 2T25",
    )

    assert outcome == "processed"
    assert service.storage.stored[0][0].startswith("dirr3/")
    assert service.extraction_service.documents[0][1] == "Direcional"
    assert service.extraction_service.documents[0][0].year == 2025
    assert service.extraction_service.documents[0][0].quarter == 2


@pytest.mark.asyncio
async def test_ingest_link_duplicado_cria_registro_ignored(db_session):
    company = Company(name="Tenda", ticker="TEND3", ri_url="https://ri.tenda.com")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    service = IngestionService(db_session)
    service.downloader = _FakeDownloader(b"mesmo pdf")
    existing = Document(
        company_id=company.id,
        title="Original",
        original_url="https://example.com/original.pdf",
        local_path="/tmp/original.pdf",
        file_hash=ingestion_module.sha256_bytes(b"mesmo pdf"),
        year=2025,
        quarter=1,
        document_type="previa_operacional",
        status=DocumentStatus.processed,
        collected_at=datetime.utcnow(),
    )
    await service.document_repo.create(existing)

    outcome = await service._ingest_link(
        company,
        "https://ri.tenda.com/previa-1t25.pdf",
        "Prévia Operacional 1T25",
    )

    docs = await service.document_repo.list_all()
    duplicate = next(doc for doc in docs if doc.status == DocumentStatus.ignored_duplicate)
    assert outcome == "ignored"
    assert duplicate.year == 2025
    assert duplicate.error_message == "Documento duplicado por hash."
