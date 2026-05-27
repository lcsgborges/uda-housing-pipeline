from fastapi import HTTPException

from app.modules.companies.repository import CompanyRepository
from app.modules.metrics.repository import MetricRepository
from app.modules.metrics.schemas import ConjunturaMetricItem, ConjunturaResponse


class MetricService:
    def __init__(self, repository: MetricRepository, company_repo: CompanyRepository):
        self.repository = repository
        self.company_repo = company_repo

    def list_all(self):
        return self.repository.list_all()

    def get_or_404(self, metric_id: int):
        metric = self.repository.get_by_id(metric_id)
        if not metric:
            raise HTTPException(status_code=404, detail="Métrica não encontrada.")
        return metric

    def conjuntura(self, empresa: str, ano: int, trimestre: int) -> ConjunturaResponse:
        companies = self.company_repo.list_all()
        company = next((c for c in companies if c.name.lower() == empresa.lower() or c.ticker.lower() == empresa.lower()), None)
        if not company:
            raise HTTPException(status_code=404, detail="Empresa não encontrada.")

        metrics = self.repository.query_conjuntura(company.id, ano, trimestre)
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
