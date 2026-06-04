from app.modules.lineage.repository import DataLineageRepository


class DataLineageService:
    def __init__(self, repository: DataLineageRepository):
        """Inicializa a camada de serviço com o repositório de linhagem."""
        self.repository = repository
