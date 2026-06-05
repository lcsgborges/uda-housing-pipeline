import pytest

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.repository import DocumentRepository


@pytest.mark.asyncio
async def test_lista_busca_e_atualiza_documentos(client, db_session):
    company = Company(name="Pacaembu", ticker="PCBU3", ri_url="https://ri.pacaembu.com")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    repository = DocumentRepository(db_session)
    document = await repository.create(
        Document(
            company_id=company.id,
            title="Prévia Operacional",
            original_url="https://example.com/previa.pdf",
            local_path="/tmp/previa.pdf",
            file_hash="hash_doc",
            year=2025,
            quarter=3,
            document_type="previa_operacional",
            status=DocumentStatus.downloaded,
            collected_at=utc_now(),
        )
    )
    document.status = DocumentStatus.processed
    await repository.update(document)

    listed = client.get("/api/documents")
    detail = client.get(f"/api/documents/{document.id}")
    missing = client.get("/api/documents/999")

    assert listed.status_code == 200
    assert listed.json()[0]["file_hash"] == "hash_doc"
    assert listed.json()[0]["file_url"] == f"/api/documents/{document.id}/file"
    assert detail.status_code == 200
    assert detail.json()["status"] == "processed"
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_abre_arquivo_local_do_documento(client, db_session, tmp_path):
    pdf_path = tmp_path / "documento.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 teste")

    company = Company(name="Pacaembu", ticker="PCBU3", ri_url="https://ri.pacaembu.com")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    repository = DocumentRepository(db_session)
    document = await repository.create(
        Document(
            company_id=company.id,
            title="Prévia Operacional",
            original_url="https://example.com/previa.pdf",
            local_path=str(pdf_path),
            file_hash="hash_doc_file",
            year=2025,
            quarter=3,
            document_type="previa_operacional",
            status=DocumentStatus.downloaded,
            collected_at=utc_now(),
        )
    )

    response = client.get(f"/api/documents/{document.id}/file")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 teste"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'inline; filename="document-{document.id}.pdf"'
    )
