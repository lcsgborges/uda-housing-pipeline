from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.metrics.models import Metric


class MetricRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_many(self, metrics: list[Metric]) -> list[Metric]:
        self.session.add_all(metrics)
        self.session.commit()
        for metric in metrics:
            self.session.refresh(metric)
        return metrics

    def list_all(self) -> list[Metric]:
        stmt = select(Metric).order_by(Metric.id.desc())
        return list(self.session.scalars(stmt).all())

    def get_by_id(self, metric_id: int) -> Metric | None:
        return self.session.get(Metric, metric_id)

    def query_conjuntura(self, company_id: int, year: int, quarter: int) -> list[Metric]:
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
        return list(self.session.scalars(stmt).all())
