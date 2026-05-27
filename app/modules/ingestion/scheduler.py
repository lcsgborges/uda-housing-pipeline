from app.core.database import SessionLocal
from app.modules.ingestion.service import IngestionService


def run_ingestion(company_id: int | None = None) -> dict:
    with SessionLocal() as session:
        service = IngestionService(session)
        return service.run(company_id=company_id)


if __name__ == "__main__":
    result = run_ingestion()
    print(result)
