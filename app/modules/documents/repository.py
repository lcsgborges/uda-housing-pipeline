from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        """Inicializa o repositório com uma sessão assíncrona de banco."""
        self.session = session

    async def list_all(self) -> list[Document]:
        """Lista documentos do mais recente para o mais antigo."""
        stmt = select(Document).order_by(Document.collected_at.desc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_by_id(self, document_id: int) -> Document | None:
        """Busca um documento pelo identificador primário."""
        return await self.session.get(Document, document_id)

    async def get_by_hash(self, file_hash: str) -> Document | None:
        """Busca o primeiro documento com o hash SHA-256 informado."""
        stmt = select(Document).where(Document.file_hash == file_hash)
        result = await self.session.scalars(stmt)
        return result.first()

    async def create(self, document: Document) -> Document:
        """Persiste um documento catalogado e atualiza seu estado em memória."""
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def update(self, document: Document) -> Document:
        """Atualiza um documento existente e recarrega seus dados."""
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document
