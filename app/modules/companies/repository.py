from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.companies.models import Company
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate


class CompanyRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: CompanyCreate) -> Company:
        company = Company(**payload.model_dump())
        self.session.add(company)
        self.session.commit()
        self.session.refresh(company)
        return company

    def list_all(self) -> list[Company]:
        stmt = select(Company).order_by(Company.name)
        return list(self.session.scalars(stmt).all())

    def get_by_id(self, company_id: int) -> Company | None:
        return self.session.get(Company, company_id)

    def update(self, company: Company, payload: CompanyUpdate) -> Company:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(company, field, value)
        self.session.add(company)
        self.session.commit()
        self.session.refresh(company)
        return company

    def delete(self, company: Company) -> None:
        self.session.delete(company)
        self.session.commit()
