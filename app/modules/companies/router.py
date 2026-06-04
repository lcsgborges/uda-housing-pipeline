from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyRead, CompanyUpdate
from app.modules.companies.service import CompanyService

router = APIRouter(prefix="/api/companies", tags=["companies"])


def get_service(session: AsyncSession = Depends(get_db_session)) -> CompanyService:
    return CompanyService(CompanyRepository(session))


@router.post("", response_model=CompanyRead, status_code=201)
async def create_company(payload: CompanyCreate, service: CompanyService = Depends(get_service)):
    return await service.create(payload)


@router.get("", response_model=list[CompanyRead])
async def list_companies(service: CompanyService = Depends(get_service)):
    return await service.list_all()


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(company_id: int, service: CompanyService = Depends(get_service)):
    return await service.get_or_404(company_id)


@router.put("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: int, payload: CompanyUpdate, service: CompanyService = Depends(get_service)
):
    return await service.update(company_id, payload)


@router.delete("/{company_id}", status_code=204, response_class=Response)
async def delete_company(company_id: int, service: CompanyService = Depends(get_service)):
    await service.delete(company_id)
    return Response(status_code=204)
