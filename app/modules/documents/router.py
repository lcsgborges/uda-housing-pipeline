from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import DocumentRead
from app.modules.documents.service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])


def get_service(session: Session = Depends(get_db_session)) -> DocumentService:
    return DocumentService(DocumentRepository(session))


@router.get("", response_model=list[DocumentRead])
def list_documents(service: DocumentService = Depends(get_service)):
    return service.list_all()


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, service: DocumentService = Depends(get_service)):
    return service.get_or_404(document_id)
