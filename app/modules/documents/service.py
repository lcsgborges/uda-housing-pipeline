from fastapi import HTTPException

from app.modules.documents.repository import DocumentRepository


class DocumentService:
    def __init__(self, repository: DocumentRepository):
        """Inicializa a camada de serviço com o repositório de documentos."""
        self.repository = repository

    async def list_all(self):
        """Retorna todos os documentos catalogados."""
        return await self.repository.list_all()

    async def get_or_404(self, document_id: int):
        """Retorna um documento por ID ou lança HTTP 404 quando ausente."""
        doc = await self.repository.get_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento não encontrado.")
        return doc
