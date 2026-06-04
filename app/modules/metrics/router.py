from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.companies.repository import CompanyRepository
from app.modules.metrics.repository import MetricRepository
from app.modules.metrics.schemas import ConjunturaResponse, MetricRead
from app.modules.metrics.service import MetricService

router = APIRouter(tags=["metrics"])

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(session: SessionDep) -> MetricService:
    return MetricService(MetricRepository(session), CompanyRepository(session))


ServiceDep = Annotated[MetricService, Depends(get_service)]


@router.get("/api/metrics", response_model=list[MetricRead])
async def list_metrics(
    service: ServiceDep,
    empresa: str | None = Query(default=None),
    ano: int | None = Query(default=None),
    trimestre: int | None = Query(default=None, ge=1, le=4),
    metrica: str | None = Query(default=None),
):
    return await service.list_all(
        empresa=empresa,
        ano=ano,
        trimestre=trimestre,
        metrica=metrica,
    )


@router.get("/api/metrics/{metric_id}", response_model=MetricRead)
async def get_metric(metric_id: int, service: ServiceDep):
    return await service.get_or_404(metric_id)


@router.get("/api/conjuntura", response_model=ConjunturaResponse)
async def get_conjuntura(
    service: ServiceDep,
    empresa: str = Query(...),
    ano: int = Query(...),
    trimestre: int = Query(..., ge=1, le=4),
):
    return await service.conjuntura(empresa=empresa, ano=ano, trimestre=trimestre)
