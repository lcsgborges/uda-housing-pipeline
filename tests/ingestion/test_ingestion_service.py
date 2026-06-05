import pytest

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.ingestion import service as ingestion_module
from app.modules.ingestion.service import IngestionService, infer_document_type, infer_period
from app.modules.storage.service import StoredObject


class _FakeDownloader:
    def __init__(self, content: bytes):
        """Inicializa downloader fake com conteúdo fixo."""
        self.content = content
        self.urls = []

    def download(self, url, destination_dir):
        """Registra download e retorna bytes configurados."""
        self.urls.append((url, destination_dir))
        return self.content


class _FakeStorage:
    def __init__(self):
        """Inicializa storage fake registrando objetos gravados."""
        self.stored = []

    def store(self, *, key: str, content: bytes):
        """Registra objeto armazenado e retorna URI local fake."""
        self.stored.append((key, content))
        return StoredObject(uri=f"file:///{key}", size_bytes=len(content))


class _FakeExtraction:
    def __init__(self):
        """Inicializa serviço de extração fake com chamadas registradas."""
        self.documents = []
        self.batch_size = None

    async def process_document(self, document, company_name):
        """Registra processamento individual de documento."""
        self.documents.append((document, company_name))

    async def process_all_pending_documents(self, batch_size=None):
        """Registra batch_size e retorna resumo de extração fake."""
        self.batch_size = batch_size
        return {"batches": 1, "selected": 2, "processed": 2, "failed": 0}


class _FakeClassification:
    def __init__(self, status=DocumentStatus.classified_useful):
        """Inicializa classificador fake com status final configurável."""
        self.status = status
        self.documents = []
        self.batch_size = None

    async def classify_document(self, document, company_name):
        """Registra classificação e aplica status configurado ao documento."""
        self.documents.append((document, company_name))
        document.status = self.status

    async def process_all_pending_documents(self, batch_size=None):
        """Registra batch_size e retorna resumo de classificação fake."""
        self.batch_size = batch_size
        return {
            "batches": 1,
            "selected": 2,
            "useful": 2,
            "ignored": 0,
            "needs_ocr": 0,
            "failed": 0,
        }


@pytest.mark.parametrize(
    ("url", "title", "expected"),
    [
        ("https://ri.com/previa-3t25.pdf", "", (2025, 3)),
        ("https://ri.com/doc.pdf", "Resultado 4T2026", (2026, 4)),
        ("https://ri.com/doc.pdf", "Relatório anual 25", (2025, None)),
        ("https://ri.com/doc.pdf", "Sem período", (None, None)),
    ],
)
def test_infer_period(url, title, expected):
    """Valida inferência de ano e trimestre por URL e título."""
    assert infer_period(url=url, title=title) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Prévia Operacional", "previa_operacional"),
        ("Previa Operacional", "previa_operacional"),
        ("Resultado Trimestral", "resultado_trimestral"),
        ("Earnings Release 1T26", "resultado_trimestral"),
        ("Relatório de Sustentabilidade", "relatorio_sustentabilidade"),
        ("ESG", "relatorio_sustentabilidade"),
        ("Comunicado ao mercado", "outro"),
    ],
)
def test_infer_document_type(text, expected):
    """Valida inferência de tipo documental por texto normalizado."""
    assert infer_document_type(text) == expected


@pytest.mark.asyncio
async def test_ingestion_run_processa_links_de_empresas_ativas(monkeypatch, db_session):
    """Garante ingestão apenas de empresas ativas."""
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
        """Simula ingestão de link garantindo empresa ativa."""
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
async def test_ingestion_run_filtra_empresa_e_contabiliza_ignorados(monkeypatch, db_session):
    """Valida filtro por empresa e contador de duplicados ignorados."""
    selected = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br", is_active=True)
    other = Company(name="Tenda", ticker="TEND3", ri_url="https://ri.tenda.com", is_active=True)
    db_session.add_all([selected, other])
    await db_session.commit()
    await db_session.refresh(selected)

    service = IngestionService(db_session)
    service.scraper = type(
        "Scraper",
        (),
        {"find_pdf_links": lambda self, url: [{"url": f"{url}/doc.pdf", "title": "Duplicado"}]},
    )()

    async def fake_ingest(company, url, title, extract_after_ingestion=True):
        """Simula link duplicado para empresa selecionada."""
        assert company.id == selected.id
        return "ignored"

    monkeypatch.setattr(service, "_ingest_link", fake_ingest)

    result = await service.run(company_id=selected.id)

    assert result == {
        "companies": 1,
        "discovered": 1,
        "processed": 0,
        "ignored_duplicates": 1,
    }


@pytest.mark.asyncio
async def test_ingestion_run_scheduled_cycle_ingere_sem_extrair_imediato(monkeypatch, db_session):
    """Garante que o ciclo agendado separa ingestão, classificação e extração."""
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br", is_active=True)
    db_session.add(company)
    await db_session.commit()

    service = IngestionService(db_session)
    service.classification_service = _FakeClassification()
    service.extraction_service = _FakeExtraction()

    async def fake_ingest(company, url, title, extract_after_ingestion=True):
        """Simula ingestão sem extração imediata no ciclo agendado."""
        assert extract_after_ingestion is False
        return "processed"

    service.scraper = type(
        "Scraper",
        (),
        {"find_pdf_links": lambda self, url: [{"url": f"{url}/doc.pdf", "title": "Prévia"}]},
    )()
    monkeypatch.setattr(service, "_ingest_link", fake_ingest)

    result = await service.run_scheduled_cycle()

    assert result["ingestion"]["processed"] == 1
    assert result["classification"] == {
        "batches": 1,
        "selected": 2,
        "useful": 2,
        "ignored": 0,
        "needs_ocr": 0,
        "failed": 0,
    }
    assert result["extraction"] == {"batches": 1, "selected": 2, "processed": 2, "failed": 0}
    assert service.classification_service.batch_size == service.settings.classification_batch_size
    assert service.extraction_service.batch_size == service.settings.extraction_batch_size


@pytest.mark.asyncio
async def test_ingest_link_novo_documento_salva_e_extrai(db_session):
    """Valida ingestão de documento novo, storage, classificação e extração."""
    company = Company(name="Direcional", ticker="DIRR3", ri_url="https://ri.direcional.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    service = IngestionService(db_session)
    service.downloader = _FakeDownloader(b"pdf novo")
    service.storage = _FakeStorage()
    service.classification_service = _FakeClassification()
    service.extraction_service = _FakeExtraction()

    outcome = await service._ingest_link(
        company,
        "https://ri.direcional.com.br/previa-2t25.pdf",
        "Prévia Operacional 2T25",
    )

    assert outcome == "processed"
    assert service.storage.stored[0][0].startswith("dirr3/")
    assert service.classification_service.documents[0][1] == "Direcional"
    assert service.extraction_service.documents[0][1] == "Direcional"
    assert service.extraction_service.documents[0][0].year == 2025
    assert service.extraction_service.documents[0][0].quarter == 2


@pytest.mark.asyncio
async def test_ingest_link_nao_extrai_documento_classificado_como_irrelevante(db_session):
    """Garante que documento irrelevante classificado não segue para extração."""
    company = Company(name="Direcional", ticker="DIRR3", ri_url="https://ri.direcional.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    service = IngestionService(db_session)
    service.downloader = _FakeDownloader(b"pdf novo")
    service.storage = _FakeStorage()
    service.classification_service = _FakeClassification(status=DocumentStatus.ignored_not_relevant)
    service.extraction_service = _FakeExtraction()

    outcome = await service._ingest_link(
        company,
        "https://ri.direcional.com.br/comunicado.pdf",
        "Comunicado",
    )

    assert outcome == "processed"
    assert service.classification_service.documents[0][1] == "Direcional"
    assert service.extraction_service.documents == []


@pytest.mark.asyncio
async def test_ingest_link_duplicado_cria_registro_ignored(db_session):
    """Garante criação de registro ignored_duplicate para hash já existente."""
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
        collected_at=utc_now(),
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
