from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.ingestion.service import IngestionService

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


def get_service(session: AsyncSession = Depends(get_db_session)) -> IngestionService:
    return IngestionService(session)


@router.post("/run")
async def run_ingestion(service: IngestionService = Depends(get_service)):
    return await service.run()


@router.post("/run/{company_id}")
async def run_ingestion_company(company_id: int, service: IngestionService = Depends(get_service)):
    return await service.run(company_id=company_id)


@router.post("/extract-batch")
async def run_extraction_batch(
    batch_size: int = 5,
    service: IngestionService = Depends(get_service),
):
    return await service.extraction_service.process_pending_documents_batch(batch_size=batch_size)
