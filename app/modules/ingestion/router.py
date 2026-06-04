from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.ingestion.service import IngestionService

router = APIRouter(prefix="/api/ingestion", tags=["Ingestão"])

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(session: SessionDep) -> IngestionService:
    """Monta o serviço de ingestão para injeção de dependência."""
    return IngestionService(session)


CompanyId = Annotated[int, Path(description="ID da empresa que terá a ingestão executada.")]
ServiceDep = Annotated[IngestionService, Depends(get_service)]


@router.post(
    "/run",
    summary="Executar ciclo de ingestão e extração",
    description=(
        "Descobre e baixa documentos novos das empresas ativas, depois processa "
        "todos os documentos pendentes em lotes."
    ),
)
async def run_ingestion(service: ServiceDep):
    """Endpoint para executar o ciclo de ingestão e extração de todas as empresas."""
    return await service.run_scheduled_cycle()


@router.post(
    "/run/{company_id}",
    summary="Executar ciclo de uma empresa",
    description=(
        "Descobre e baixa documentos novos de uma empresa ativa, depois processa "
        "documentos pendentes em lotes."
    ),
)
async def run_ingestion_company(
    company_id: CompanyId,
    service: ServiceDep,
):
    """Endpoint para executar o ciclo de ingestão e extração de uma empresa."""
    return await service.run_scheduled_cycle(company_id=company_id)


@router.post(
    "/extract-batch",
    summary="Executar extração em lote",
    description="Processa documentos pendentes em lote pela LLM.",
)
async def run_extraction_batch(
    service: ServiceDep,
    batch_size: int = Query(
        default=5,
        ge=1,
        description="Quantidade máxima de documentos no lote.",
    ),
):
    """Endpoint para processar documentos pendentes em lote pela LLM."""
    return await service.extraction_service.process_pending_documents_batch(batch_size=batch_size)
