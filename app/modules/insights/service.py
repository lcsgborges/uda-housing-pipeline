from sqlalchemy import or_, select

from app.core.text import normalize_for_search
from app.modules.companies.models import Company
from app.modules.companies.repository import CompanyRepository
from app.modules.insights.repository import DocumentInsightRepository


class DocumentInsightService:
    def __init__(
        self,
        repository: DocumentInsightRepository,
        company_repository: CompanyRepository,
    ):
        """Inicializa serviço de consulta de insights documentais."""
        self.repository = repository
        self.company_repository = company_repository

    async def list_insights(
        self,
        *,
        empresa: str | None = None,
        document_id: int | None = None,
        insight_type: str | None = None,
        topic: str | None = None,
        ano: int | None = None,
    ):
        """Lista insights com resolução opcional de empresa por nome ou ticker."""
        company_id = None
        if empresa:
            company = await _get_company_by_name_or_ticker(self.company_repository, empresa)
            if not company:
                return []
            company_id = company.id
        return await self.repository.query(
            company_id=company_id,
            document_id=document_id,
            insight_type=insight_type,
            topic=topic,
            period_year=ano,
        )


async def _get_company_by_name_or_ticker(
    repository: CompanyRepository,
    value: str,
) -> Company | None:
    """Resolve empresa por nome ou ticker ignorando acentos e caixa."""
    normalized = normalize_for_search(value)
    stmt = select(Company).where(
        or_(
            Company.ticker.ilike(value),
            Company.name.ilike(value),
        )
    )
    result = await repository.session.scalars(stmt)
    direct_match = result.first()
    if direct_match:
        return direct_match

    companies = await repository.list_all()
    return next(
        (
            company
            for company in companies
            if normalize_for_search(company.name) == normalized
            or normalize_for_search(company.ticker) == normalized
        ),
        None,
    )
