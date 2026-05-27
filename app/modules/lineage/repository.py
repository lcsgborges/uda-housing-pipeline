from sqlalchemy.orm import Session

from app.modules.lineage.models import DataLineage


class DataLineageRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_many(self, rows: list[DataLineage]) -> list[DataLineage]:
        self.session.add_all(rows)
        self.session.commit()
        return rows
