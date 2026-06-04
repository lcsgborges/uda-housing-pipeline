from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lineage.models import DataLineage


class DataLineageRepository:
    def __init__(self, session: AsyncSession):
        """Inicializa o repositório com uma sessão assíncrona de banco."""
        self.session = session

    async def create_many(self, rows: list[DataLineage]) -> list[DataLineage]:
        """Persiste registros de linhagem em lote."""
        self.session.add_all(rows)
        await self.session.commit()
        return rows
