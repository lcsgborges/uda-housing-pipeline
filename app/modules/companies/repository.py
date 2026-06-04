from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.companies.models import Company
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payload: CompanyCreate) -> Company:
        data = payload.model_dump(mode="json")
        company = Company(**data)
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def list_all(self) -> list[Company]:
        stmt = select(Company).order_by(Company.name)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_by_id(self, company_id: int) -> Company | None:
        return await self.session.get(Company, company_id)

    async def update(self, company: Company, payload: CompanyUpdate) -> Company:
        for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
            setattr(company, field, value)
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def delete(self, company: Company) -> None:
        await self.session.delete(company)
        await self.session.commit()
