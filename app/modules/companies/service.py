from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate


class CompanyService:
    def __init__(self, repository: CompanyRepository):
        """Inicializa a camada de serviço com o repositório de empresas."""
        self.repository = repository

    async def create(self, payload: CompanyCreate):
        """Cria uma empresa e traduz conflitos de unicidade para HTTP 409."""
        try:
            return await self.repository.create(payload)
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Empresa com mesmo nome ou ticker já cadastrada.",
            ) from exc

    async def list_all(self):
        """Retorna todas as empresas cadastradas."""
        return await self.repository.list_all()

    async def get_or_404(self, company_id: int):
        """Retorna uma empresa por ID ou lança HTTP 404 quando ausente."""
        company = await self.repository.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Empresa não encontrada.")
        return company

    async def update(self, company_id: int, payload: CompanyUpdate):
        """Atualiza uma empresa existente depois de validar sua existência."""
        company = await self.get_or_404(company_id)
        return await self.repository.update(company, payload)

    async def delete(self, company_id: int):
        """Remove uma empresa existente depois de validar sua existência."""
        company = await self.get_or_404(company_id)
        await self.repository.delete(company)
