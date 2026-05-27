from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[Document]:
        stmt = select(Document).order_by(Document.collected_at.desc())
        return list(self.session.scalars(stmt).all())

    def get_by_id(self, document_id: int) -> Document | None:
        return self.session.get(Document, document_id)

    def get_by_hash(self, file_hash: str) -> Document | None:
        stmt = select(Document).where(Document.file_hash == file_hash)
        return self.session.scalars(stmt).first()

    def create(self, document: Document) -> Document:
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def update(self, document: Document) -> Document:
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document
