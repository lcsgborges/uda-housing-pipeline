from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lineage.models import DataLineage


class DataLineageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_many(self, rows: list[DataLineage]) -> list[DataLineage]:
        self.session.add_all(rows)
        await self.session.commit()
        return rows
