import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.ingestion.service import IngestionService

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


async def run_ingestion(company_id: int | None = None) -> dict:
    async with SessionLocal() as session:
        service = IngestionService(session)
        return await service.run(company_id=company_id)


def run_ingestion_sync(company_id: int | None = None) -> dict:
    return asyncio.run(run_ingestion(company_id=company_id))


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_ingestion_sync,
        "interval",
        minutes=settings.ingestion_poll_interval_minutes,
        id="ingestion_polling",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler de ingestão iniciado (intervalo=%s min)",
        settings.ingestion_poll_interval_minutes,
    )
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler de ingestão finalizado")
    _scheduler = None


if __name__ == "__main__":
    result = run_ingestion_sync()
    print(result)
