from fastapi import HTTPException

from app.modules.documents.repository import DocumentRepository
from app.modules.storage.service import ObjectStorage, build_object_storage


class DocumentService:
    def __init__(self, repository: DocumentRepository, storage: ObjectStorage | None = None):
        """Inicializa a camada de serviço com o repositório de documentos."""
        self.repository = repository
        self._storage = storage

    async def list_all(self):
        """Retorna todos os documentos catalogados."""
        return await self.repository.list_all()

    async def get_or_404(self, document_id: int):
        """Retorna um documento por ID ou lança HTTP 404 quando ausente."""
        doc = await self.repository.get_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento não encontrado.")
        return doc

    async def read_file_or_404(self, document_id: int) -> tuple[object, bytes]:
        """Lê os bytes do arquivo associado a um documento."""
        doc = await self.get_or_404(document_id)
        if not doc.local_path:
            raise HTTPException(status_code=404, detail="Documento sem arquivo armazenado.")
        try:
            return doc, self.storage.read(doc.local_path)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="Arquivo do documento não encontrado.",
            ) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Falha ao ler arquivo: {exc}") from exc

    @property
    def storage(self) -> ObjectStorage:
        """Constrói o storage sob demanda para evitar custo em consultas de metadados."""
        if self._storage is None:
            self._storage = build_object_storage()
        return self._storage
