from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.models_registry import Company, DataLineage, Document, DocumentInsight, Metric
from app.modules.companies.router import router as companies_router
from app.modules.documents.router import router as documents_router
from app.modules.ingestion.router import router as ingestion_router
from app.modules.ingestion.scheduler import start_scheduler, stop_scheduler
from app.modules.insights.router import router as insights_router
from app.modules.metrics.router import router as metrics_router

configure_logging()

_ = (Company, Document, Metric, DataLineage, DocumentInsight)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa schema e scheduler opcional durante o ciclo de vida da API."""
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


app = FastAPI(
    title="Pipeline UDA",
    description=(
        "API para coletar documentos de Relações com Investidores, extrair métricas "
        "habitacionais com LLM e consultar dados de conjuntura."
    ),
    lifespan=lifespan,
)

app.include_router(companies_router)
app.include_router(documents_router)
app.include_router(ingestion_router)
app.include_router(insights_router)
app.include_router(metrics_router)


@app.get(
    "/health",
    summary="Verificar saúde",
    description="Retorna o estado básico de disponibilidade da API.",
)
async def health():
    """Retorna o status básico de disponibilidade da aplicação."""
    return {"status": "ok"}
