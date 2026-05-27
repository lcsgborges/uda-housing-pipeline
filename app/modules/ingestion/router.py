from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.modules.ingestion.service import IngestionService

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


def get_service(session: Session = Depends(get_db_session)) -> IngestionService:
    return IngestionService(session)


@router.post("/run")
def run_ingestion(service: IngestionService = Depends(get_service)):
    return service.run()


@router.post("/run/{company_id}")
def run_ingestion_company(company_id: int, service: IngestionService = Depends(get_service)):
    return service.run(company_id=company_id)
