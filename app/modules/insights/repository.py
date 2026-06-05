from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights.models import DocumentInsight


class DocumentInsightRepository:
    def __init__(self, session: AsyncSession):
        """Inicializa o repositório de insights com uma sessão assíncrona."""
        self.session = session

    async def create_many(self, insights: list[DocumentInsight]) -> list[DocumentInsight]:
        """Persiste insights extraídos e recarrega seus identificadores."""
        self.session.add_all(insights)
        await self.session.commit()
        for insight in insights:
            await self.session.refresh(insight)
        return insights

    async def query(
        self,
        *,
        company_id: int | None = None,
        document_id: int | None = None,
        insight_type: str | None = None,
        topic: str | None = None,
        period_year: int | None = None,
    ) -> list[DocumentInsight]:
        """Consulta insights com filtros opcionais."""
        stmt = select(DocumentInsight)
        filters = []
        if company_id is not None:
            filters.append(DocumentInsight.company_id == company_id)
        if document_id is not None:
            filters.append(DocumentInsight.document_id == document_id)
        if insight_type:
            filters.append(DocumentInsight.insight_type == insight_type)
        if topic:
            filters.append(DocumentInsight.topic == topic)
        if period_year is not None:
            filters.append(DocumentInsight.period_year == period_year)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(DocumentInsight.document_id.desc(), DocumentInsight.id.asc())
        result = await self.session.scalars(stmt)
        return list(result.all())
