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
BatchId = Annotated[str, Path(description="ID do batch assíncrono criado na OpenAI.")]
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
    "/classify-batch",
    summary="Executar classificação em lote",
    description="Classifica documentos baixados por utilidade antes da extração.",
)
async def run_classification_batch(
    service: ServiceDep,
    batch_size: int = Query(
        default=5,
        ge=1,
        description="Quantidade máxima de documentos no lote.",
    ),
):
    """Endpoint para classificar documentos pendentes por utilidade."""
    return await service.classification_service.process_pending_documents_batch(
        batch_size=batch_size
    )


@router.post(
    "/extract-batch",
    summary="Executar extração em lote",
    description="Processa documentos classificados como úteis em lote pela LLM.",
)
async def run_extraction_batch(
    service: ServiceDep,
    batch_size: int = Query(
        default=1,
        ge=1,
        description="Quantidade máxima de documentos no lote.",
    ),
):
    """Endpoint para processar documentos pendentes em lote pela LLM."""
    return await service.extraction_service.process_pending_documents_batch(batch_size=batch_size)


@router.post(
    "/openai-batch/submit",
    summary="Submeter extração assíncrona na OpenAI Batch API",
    description=(
        "Seleciona documentos úteis, monta uma linha JSONL por parte documental e "
        "cria um batch assíncrono no endpoint /v1/responses."
    ),
)
async def submit_openai_batch(
    service: ServiceDep,
    batch_size: int = Query(
        default=1,
        ge=1,
        description="Quantidade máxima de documentos selecionados para o batch.",
    ),
):
    """Endpoint para submeter extração offline pela OpenAI Batch API."""
    return await service.extraction_service.submit_openai_extraction_batch(
        batch_size=batch_size
    )


@router.get(
    "/openai-batch/{batch_id}",
    summary="Consultar status de batch OpenAI",
)
async def get_openai_batch_status(batch_id: BatchId, service: ServiceDep):
    """Endpoint para consultar status de um batch assíncrono da OpenAI."""
    return service.extraction_service.get_openai_extraction_batch_status(batch_id)


@router.post(
    "/openai-batch/{batch_id}/import",
    summary="Importar resultado de batch OpenAI",
)
async def import_openai_batch(batch_id: BatchId, service: ServiceDep):
    """Endpoint para baixar output_file_id e persistir métricas/insights."""
    return await service.extraction_service.import_openai_extraction_batch(batch_id)
