from fastapi import HTTPException

from app.modules.documents.repository import DocumentRepository


class DocumentService:
    def __init__(self, repository: DocumentRepository):
        self.repository = repository

    def list_all(self):
        return self.repository.list_all()

    def get_or_404(self, document_id: int):
        doc = self.repository.get_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento não encontrado.")
        return doc
