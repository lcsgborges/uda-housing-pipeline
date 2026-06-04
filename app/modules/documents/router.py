from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import DocumentRead
from app.modules.documents.service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["Documentos"])

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(session: SessionDep) -> DocumentService:
    """Monta o serviço de documentos para injeção de dependência."""
    return DocumentService(DocumentRepository(session))


DocumentId = Annotated[int, Path(description="ID do documento catalogado.")]
ServiceDep = Annotated[DocumentService, Depends(get_service)]


@router.get(
    "",
    response_model=list[DocumentRead],
    summary="Listar documentos",
    description="Lista documentos encontrados, baixados, processados ou ignorados por duplicidade.",
)
async def list_documents(service: ServiceDep):
    """Endpoint para listar documentos catalogados."""
    return await service.list_all()


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Consultar documento",
    description="Retorna os dados de um documento catalogado.",
)
async def get_document(document_id: DocumentId, service: ServiceDep):
    """Endpoint para consultar um documento por ID."""
    return await service.get_or_404(document_id)
