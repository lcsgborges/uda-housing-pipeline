from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.documents.service import DocumentService


class StubDocumentRepository:
    def __init__(self, document=None):
        """Inicializa repositório fake com documento opcional."""
        self.document = document

    async def list_all(self):
        """Lista o documento fake quando configurado."""
        return [self.document] if self.document else []

    async def get_by_id(self, document_id: int):
        """Retorna o documento fake independentemente do ID."""
        return self.document


class StubStorage:
    def __init__(self, content=b"pdf"):
        """Inicializa storage fake com conteúdo fixo."""
        self.content = content
        self.read_uris = []

    def read(self, uri):
        """Registra URI lida e retorna o conteúdo configurado."""
        self.read_uris.append(uri)
        return self.content


@pytest.mark.asyncio
async def test_document_service_get_or_404_missing():
    """Valida listagem vazia e HTTP 404 para documento ausente."""
    service = DocumentService(StubDocumentRepository())

    assert await service.list_all() == []

    with pytest.raises(HTTPException) as excinfo:
        await service.get_or_404(999)

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_document_service_get_or_404_found():
    """Garante retorno do documento quando o repositório o encontra."""
    document = SimpleNamespace(id=1)
    service = DocumentService(StubDocumentRepository(document=document))

    assert await service.get_or_404(1) is document


@pytest.mark.asyncio
async def test_document_service_read_file_or_404():
    """Valida leitura de arquivo por URI de storage."""
    document = SimpleNamespace(id=1, local_path="s3://bucket/doc.pdf")
    storage = StubStorage(content=b"%PDF")
    service = DocumentService(StubDocumentRepository(document=document), storage=storage)

    found_document, content = await service.read_file_or_404(1)

    assert found_document is document
    assert content == b"%PDF"
    assert storage.read_uris == ["s3://bucket/doc.pdf"]


@pytest.mark.asyncio
async def test_document_service_read_file_sem_arquivo():
    """Garante HTTP 404 quando documento não possui arquivo associado."""
    document = SimpleNamespace(id=1, local_path=None)
    service = DocumentService(StubDocumentRepository(document=document), storage=StubStorage())

    with pytest.raises(HTTPException) as excinfo:
        await service.read_file_or_404(1)

    assert excinfo.value.status_code == 404
