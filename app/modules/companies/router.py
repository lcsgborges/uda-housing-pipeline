from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyRead, CompanyUpdate
from app.modules.companies.service import CompanyService

router = APIRouter(prefix="/api/companies", tags=["companies"])

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(session: SessionDep) -> CompanyService:
    return CompanyService(CompanyRepository(session))


ServiceDep = Annotated[CompanyService, Depends(get_service)]


@router.post("", response_model=CompanyRead, status_code=201)
async def create_company(payload: CompanyCreate, service: ServiceDep):
    return await service.create(payload)


@router.get("", response_model=list[CompanyRead])
async def list_companies(service: ServiceDep):
    return await service.list_all()


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(company_id: int, service: ServiceDep):
    return await service.get_or_404(company_id)


@router.put("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: int,
    payload: CompanyUpdate,
    service: ServiceDep,
):
    return await service.update(company_id, payload)


@router.delete("/{company_id}", status_code=204, response_class=Response)
async def delete_company(company_id: int, service: ServiceDep):
    await service.delete(company_id)
    return Response(status_code=204)
