from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.modules.companies.repository import CompanyRepository
from app.modules.metrics.repository import MetricRepository
from app.modules.metrics.schemas import ConjunturaResponse, MetricRead
from app.modules.metrics.service import MetricService

router = APIRouter(tags=["metrics"])


def get_service(session: Session = Depends(get_db_session)) -> MetricService:
    return MetricService(MetricRepository(session), CompanyRepository(session))


@router.get("/api/metrics", response_model=list[MetricRead])
def list_metrics(service: MetricService = Depends(get_service)):
    return service.list_all()


@router.get("/api/metrics/{metric_id}", response_model=MetricRead)
def get_metric(metric_id: int, service: MetricService = Depends(get_service)):
    return service.get_or_404(metric_id)


@router.get("/api/conjuntura", response_model=ConjunturaResponse)
def get_conjuntura(
    empresa: str = Query(...),
    ano: int = Query(...),
    trimestre: int = Query(..., ge=1, le=4),
    service: MetricService = Depends(get_service),
):
    return service.conjuntura(empresa=empresa, ano=ano, trimestre=trimestre)
