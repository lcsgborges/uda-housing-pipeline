import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.companies.models import Company
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate
from app.modules.companies.service import CompanyService


@pytest.mark.asyncio
async def test_company_repository_crud_branches(db_session):
    repository = CompanyRepository(db_session)
    payload = CompanyCreate(
        name="Tenda",
        ticker="TEND3",
        ri_url="https://ri.tenda.com",
    )

    company = await repository.create(payload)
    listed = await repository.list_all()
    fetched = await repository.get_by_id(company.id)
    updated = await repository.update(
        company,
        CompanyUpdate(name="Construtora Tenda", is_active=False),
    )

    assert listed[0].id == company.id
    assert fetched is not None
    assert fetched.id == company.id
    assert updated.name == "Construtora Tenda"
    assert updated.is_active is False

    await repository.delete(updated)

    assert await repository.get_by_id(company.id) is None


class StubCompanyRepository:
    def __init__(self, company: Company | None = None, fail_on_create: bool = False):
        self.company = company
        self.fail_on_create = fail_on_create
        self.updated_payload = None
        self.deleted = False

    async def create(self, payload):
        if self.fail_on_create:
            raise IntegrityError("statement", {}, Exception("duplicate"))
        return self.company

    async def list_all(self):
        return [self.company] if self.company else []

    async def get_by_id(self, company_id: int):
        return self.company

    async def update(self, company: Company, payload: CompanyUpdate):
        self.updated_payload = payload
        return company

    async def delete(self, company: Company):
        self.deleted = True


@pytest.mark.asyncio
async def test_company_service_conflict_update_delete_and_not_found():
    company = Company(
        name="MRV",
        ticker="MRVE3",
        ri_url="https://ri.mrv.com.br",
        is_active=True,
    )
    repository = StubCompanyRepository(company=company)
    service = CompanyService(repository)

    listed = await service.list_all()
    got = await service.get_or_404(1)
    updated = await service.update(1, CompanyUpdate(is_active=False))
    await service.delete(1)

    assert listed == [company]
    assert got is company
    assert updated is company
    assert repository.updated_payload is not None
    assert repository.deleted is True

    missing_service = CompanyService(StubCompanyRepository())
    with pytest.raises(HTTPException) as excinfo:
        await missing_service.get_or_404(999)
    assert excinfo.value.status_code == 404

    conflict_service = CompanyService(StubCompanyRepository(fail_on_create=True))
    with pytest.raises(HTTPException) as excinfo:
        await conflict_service.create(
            CompanyCreate(
                name="Cury",
                ticker="CURY3",
                ri_url="https://ri.cury.com.br",
            )
        )
    assert excinfo.value.status_code == 409
