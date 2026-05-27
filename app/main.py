from fastapi import FastAPI

from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.models_registry import Company, DataLineage, Document, Metric
from app.modules.companies.router import router as companies_router
from app.modules.documents.router import router as documents_router
from app.modules.ingestion.router import router as ingestion_router
from app.modules.metrics.router import router as metrics_router

configure_logging()
app = FastAPI(title="Pipeline UDA")

app.include_router(companies_router)
app.include_router(documents_router)
app.include_router(ingestion_router)
app.include_router(metrics_router)

_ = (Company, Document, Metric, DataLineage)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}
