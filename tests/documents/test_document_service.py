from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.documents.service import DocumentService


class StubDocumentRepository:
    def __init__(self, document=None):
        self.document = document

    async def list_all(self):
        return [self.document] if self.document else []

    async def get_by_id(self, document_id: int):
        return self.document


class StubStorage:
    def __init__(self, content=b"pdf"):
        self.content = content
        self.read_uris = []

    def read(self, uri):
        self.read_uris.append(uri)
        return self.content


@pytest.mark.asyncio
async def test_document_service_get_or_404_missing():
    service = DocumentService(StubDocumentRepository())

    assert await service.list_all() == []

    with pytest.raises(HTTPException) as excinfo:
        await service.get_or_404(999)

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_document_service_get_or_404_found():
    document = SimpleNamespace(id=1)
    service = DocumentService(StubDocumentRepository(document=document))

    assert await service.get_or_404(1) is document


@pytest.mark.asyncio
async def test_document_service_read_file_or_404():
    document = SimpleNamespace(id=1, local_path="s3://bucket/doc.pdf")
    storage = StubStorage(content=b"%PDF")
    service = DocumentService(StubDocumentRepository(document=document), storage=storage)

    found_document, content = await service.read_file_or_404(1)

    assert found_document is document
    assert content == b"%PDF"
    assert storage.read_uris == ["s3://bucket/doc.pdf"]


@pytest.mark.asyncio
async def test_document_service_read_file_sem_arquivo():
    document = SimpleNamespace(id=1, local_path=None)
    service = DocumentService(StubDocumentRepository(document=document), storage=StubStorage())

    with pytest.raises(HTTPException) as excinfo:
        await service.read_file_or_404(1)

    assert excinfo.value.status_code == 404
