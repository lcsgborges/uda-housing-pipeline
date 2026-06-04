from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[Document]:
        stmt = select(Document).order_by(Document.collected_at.desc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_by_id(self, document_id: int) -> Document | None:
        return await self.session.get(Document, document_id)

    async def get_by_hash(self, file_hash: str) -> Document | None:
        stmt = select(Document).where(Document.file_hash == file_hash)
        result = await self.session.scalars(stmt)
        return result.first()

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def update(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document
