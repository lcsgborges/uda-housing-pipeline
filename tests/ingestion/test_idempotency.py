import pytest

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.repository import DocumentRepository


@pytest.mark.asyncio
async def test_deteccao_duplicidade_por_hash(db_session):
    """Valida busca de documento existente pelo hash de arquivo."""
    company = Company(name="Tenda", ticker="TEND3", ri_url="https://ri.tenda.com", is_active=True)
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

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
        collected_at=utc_now(),
    )
    await repository.create(doc)

    existing = await repository.get_by_hash("hash_unico")
    assert existing is not None
    assert existing.file_hash == "hash_unico"
