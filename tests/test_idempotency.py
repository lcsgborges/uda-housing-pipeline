import asyncio
from datetime import datetime

from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.repository import DocumentRepository


def test_deteccao_duplicidade_por_hash(db_session):
    company = Company(name="Tenda", ticker="TEND3", ri_url="https://ri.tenda.com", is_active=True)
    db_session.add(company)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(company))

    repository = DocumentRepository(db_session)
    doc = Document(
        company_id=company.id,
        title="Documento",
        original_url="https://example.com/doc.pdf",
        local_path="/tmp/doc.pdf",
        file_hash="hash_unico",
        year=2025,
        quarter=3,
        document_type="previa_operacional",
        status=DocumentStatus.processed,
        collected_at=datetime.utcnow(),
    )
    asyncio.run(repository.create(doc))

    existing = asyncio.run(repository.get_by_hash("hash_unico"))
    assert existing is not None
    assert existing.file_hash == "hash_unico"
