from fastapi import HTTPException

from app.modules.companies.repository import CompanyRepository
from app.modules.metrics.repository import MetricRepository
from app.modules.metrics.schemas import ConjunturaMetricItem, ConjunturaResponse


class MetricService:
    def __init__(self, repository: MetricRepository, company_repo: CompanyRepository):
        self.repository = repository
        self.company_repo = company_repo

    async def list_all(
        self,
        *,
        empresa: str | None = None,
        ano: int | None = None,
        trimestre: int | None = None,
        metrica: str | None = None,
    ):
        company_id = None
        if empresa:
            company_id = (await self._get_company_or_404(empresa)).id
        return await self.repository.query(
            company_id=company_id,
            year=ano,
            quarter=trimestre,
            metric_name=metrica,
        )

    async def get_or_404(self, metric_id: int):
        metric = await self.repository.get_by_id(metric_id)
        if not metric:
            raise HTTPException(status_code=404, detail="Métrica não encontrada.")
        return metric

    async def conjuntura(self, empresa: str, ano: int, trimestre: int) -> ConjunturaResponse:
        company = await self._get_company_or_404(empresa)
        metrics = await self.repository.query_conjuntura(company.id, ano, trimestre)
        return ConjunturaResponse(
            empresa=company.name,
            ano=ano,
            trimestre=trimestre,
            metricas=[
                ConjunturaMetricItem(
                    nome=m.metric_name,
                    valor=m.value,
                    unidade=m.unit or m.currency,
                    fonte={
                        "documento": m.document.title if m.document else None,
                        "url": m.document.original_url if m.document else None,
                        "pagina": m.source_page,
                        "trecho": m.source_excerpt,
                    },
                    confianca=m.confidence,
                )
                for m in metrics
            ],
        )

    async def _get_company_or_404(self, empresa: str):
        companies = await self.company_repo.list_all()
        empresa_normalizada = empresa.lower()
        company = next(
            (
                c
                for c in companies
                if c.name.lower() == empresa_normalizada or c.ticker.lower() == empresa_normalizada
            ),
            None,
        )
        if not company:
            raise HTTPException(status_code=404, detail="Empresa não encontrada.")
        return company
