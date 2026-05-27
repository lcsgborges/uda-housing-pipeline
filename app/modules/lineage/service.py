from app.modules.lineage.repository import DataLineageRepository


class DataLineageService:
    def __init__(self, repository: DataLineageRepository):
        self.repository = repository
