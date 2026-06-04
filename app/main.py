from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.models_registry import Company, DataLineage, Document, Metric
from app.modules.companies.router import router as companies_router
from app.modules.documents.router import router as documents_router
from app.modules.ingestion.router import router as ingestion_router
from app.modules.ingestion.scheduler import start_scheduler, stop_scheduler
from app.modules.metrics.router import router as metrics_router

configure_logging()

_ = (Company, Document, Metric, DataLineage)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    settings = get_settings()
    if settings.enable_ingestion_scheduler:
        start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="Pipeline UDA", lifespan=lifespan)

app.include_router(companies_router)
app.include_router(documents_router)
app.include_router(ingestion_router)
app.include_router(metrics_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
