import asyncio

from app.core.database import SessionLocal
from app.modules.ingestion.service import IngestionService


async def _run_ingestion_async() -> dict:
    async with SessionLocal() as session:
        service = IngestionService(session)
        # Ingestao separada da extracao para reduzir custo/controle por DAG.
        return await service.run(extract_after_ingestion=False)


async def _run_extraction_batch_async(batch_size: int) -> dict:
    async with SessionLocal() as session:
        service = IngestionService(session)
        return await service.extraction_service.process_pending_documents_batch(batch_size=batch_size)


def airflow_ingestion_task() -> dict:
    return asyncio.run(_run_ingestion_async())


def airflow_extraction_batch_task(batch_size: int = 10) -> dict:
    return asyncio.run(_run_extraction_batch_async(batch_size=batch_size))
