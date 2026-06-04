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


@pytest.mark.asyncio
async def test_document_service_get_or_404_missing():
    service = DocumentService(StubDocumentRepository())

    assert await service.list_all() == []

    with pytest.raises(HTTPException) as excinfo:
        await service.get_or_404(999)

    assert excinfo.value.status_code == 404
