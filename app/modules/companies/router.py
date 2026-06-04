from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyRead, CompanyUpdate
from app.modules.companies.service import CompanyService

router = APIRouter(prefix="/api/companies", tags=["Empresas"])

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(session: SessionDep) -> CompanyService:
    """Monta o serviço de empresas para injeção de dependência."""
    return CompanyService(CompanyRepository(session))


ServiceDep = Annotated[CompanyService, Depends(get_service)]


CompanyId = Annotated[int, Path(description="ID da empresa cadastrada.")]


@router.post(
    "",
    response_model=CompanyRead,
    status_code=201,
    summary="Cadastrar empresa",
    description=(
        "Cadastra uma empresa monitorada, incluindo ticker e URL de Relações com Investidores."
    ),
)
async def create_company(payload: CompanyCreate, service: ServiceDep):
    """Endpoint para cadastrar uma empresa monitorada."""
    return await service.create(payload)


@router.get(
    "",
    response_model=list[CompanyRead],
    summary="Listar empresas",
    description="Lista as empresas cadastradas em ordem alfabética.",
)
async def list_companies(service: ServiceDep):
    """Endpoint para listar empresas cadastradas."""
    return await service.list_all()


@router.get(
    "/{company_id}",
    response_model=CompanyRead,
    summary="Consultar empresa",
    description="Retorna os dados de uma empresa cadastrada.",
)
async def get_company(company_id: CompanyId, service: ServiceDep):
    """Endpoint para consultar uma empresa por ID."""
    return await service.get_or_404(company_id)


@router.put(
    "/{company_id}",
    response_model=CompanyRead,
    summary="Atualizar empresa",
    description="Atualiza os campos enviados de uma empresa cadastrada.",
)
async def update_company(
    company_id: CompanyId,
    payload: CompanyUpdate,
    service: ServiceDep,
):
    """Endpoint para atualizar parcialmente uma empresa."""
    return await service.update(company_id, payload)


@router.delete(
    "/{company_id}",
    status_code=204,
    response_class=Response,
    summary="Remover empresa",
    description="Remove uma empresa cadastrada e seus dados relacionados.",
)
async def delete_company(company_id: CompanyId, service: ServiceDep):
    """Endpoint para remover uma empresa por ID."""
    await service.delete(company_id)
    return Response(status_code=204)
