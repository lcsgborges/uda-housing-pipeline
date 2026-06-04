from fastapi import HTTPException

from app.core.text import normalize_for_search
from app.modules.companies.repository import CompanyRepository
from app.modules.metrics.catalog import (
    canonical_metric_name,
    find_metric_definition,
    metric_priority,
)
from app.modules.metrics.models import Metric
from app.modules.metrics.repository import MetricRepository
from app.modules.metrics.schemas import (
    ConjunturaMetricItem,
    ConjunturaQuality,
    ConjunturaResponse,
)


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
            metric_name=canonical_metric_name(metrica) if metrica else None,
        )

    async def get_or_404(self, metric_id: int):
        metric = await self.repository.get_by_id(metric_id)
        if not metric:
            raise HTTPException(status_code=404, detail="Métrica não encontrada.")
        return metric

    async def conjuntura(self, empresa: str, ano: int, trimestre: int) -> ConjunturaResponse:
        company = await self._get_company_or_404(empresa)
        raw_metrics = await self.repository.query_conjuntura(company.id, ano, trimestre)
        metrics = _select_gold_metrics(raw_metrics)
        return ConjunturaResponse(
            empresa=company.name,
            ano=ano,
            trimestre=trimestre,
            metricas=[
                ConjunturaMetricItem(
                    nome=canonical_metric_name(m.metric_name),
                    categoria=m.metric_category or _catalog_category(m.metric_name),
                    valor=m.value,
                    unidade=m.unit or m.currency,
                    fonte={
                        "documento": m.document.title if m.document else None,
                        "url": m.document.original_url if m.document else None,
                        "pagina": m.source_page,
                        "trecho": m.source_excerpt,
                    },
                    confianca=m.confidence,
                    qualidade=_metric_quality(m),
                )
                for m in metrics
            ],
        )

    async def _get_company_or_404(self, empresa: str):
        companies = await self.company_repo.list_all()
        empresa_normalizada = normalize_for_search(empresa)
        company = next(
            (
                c
                for c in companies
                if normalize_for_search(c.name) == empresa_normalizada
                or normalize_for_search(c.ticker) == empresa_normalizada
            ),
            None,
        )
        if not company:
            raise HTTPException(status_code=404, detail="Empresa não encontrada.")
        return company


def _select_gold_metrics(metrics: list[Metric]) -> list[Metric]:
    best_by_name: dict[str, Metric] = {}
    for metric in metrics:
        name = canonical_metric_name(metric.metric_name)
        current = best_by_name.get(name)
        if current is None or _metric_rank(metric) > _metric_rank(current):
            best_by_name[name] = metric
    return sorted(
        best_by_name.values(),
        key=lambda item: (metric_priority(item.metric_name), item.metric_name),
    )


def _metric_rank(metric: Metric) -> tuple[int, float, int]:
    return (_metric_quality_score(metric), metric.confidence, metric.id or 0)


def _metric_quality(metric: Metric) -> ConjunturaQuality:
    bounded_score = _metric_quality_score(metric)
    return ConjunturaQuality(
        camada="gold",
        nivel=_quality_level(bounded_score),
        score=bounded_score,
    )


def _metric_quality_score(metric: Metric) -> int:
    score = round(metric.confidence * 100)
    score += 8 if metric.value is not None else -20
    score += 4 if metric.source_page is not None else -6
    score += 4 if metric.source_excerpt else -6
    score += 4 if find_metric_definition(metric.metric_name) else -4
    return max(0, min(100, score))


def _quality_level(score: int) -> str:
    if score >= 85:
        return "alta"
    if score >= 65:
        return "media"
    return "baixa"


def _catalog_category(metric_name: str) -> str | None:
    definition = find_metric_definition(metric_name)
    return definition.category if definition else None
