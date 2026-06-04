from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.metrics.models import Metric


class MetricRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_many(self, metrics: list[Metric]) -> list[Metric]:
        self.session.add_all(metrics)
        await self.session.commit()
        for metric in metrics:
            await self.session.refresh(metric)
        return metrics

    async def list_all(self) -> list[Metric]:
        stmt = select(Metric).order_by(Metric.id.desc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def query(
        self,
        *,
        company_id: int | None = None,
        year: int | None = None,
        quarter: int | None = None,
        metric_name: str | None = None,
    ) -> list[Metric]:
        filters = []
        if company_id is not None:
            filters.append(Metric.company_id == company_id)
        if year is not None:
            filters.append(Metric.period_year == year)
        if quarter is not None:
            filters.append(Metric.period_quarter == quarter)
        if metric_name:
            filters.append(Metric.metric_name == metric_name)

        stmt = select(Metric).order_by(Metric.id.desc())
        if filters:
            stmt = stmt.where(and_(*filters))
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_by_id(self, metric_id: int) -> Metric | None:
        return await self.session.get(Metric, metric_id)

    async def query_conjuntura(self, company_id: int, year: int, quarter: int) -> list[Metric]:
        stmt = (
            select(Metric)
            .options(joinedload(Metric.document))
            .where(
                and_(
                    Metric.company_id == company_id,
                    Metric.period_year == year,
                    Metric.period_quarter == quarter,
                )
            )
            .order_by(Metric.metric_name)
        )
        result = await self.session.scalars(stmt)
        return list(result.all())
