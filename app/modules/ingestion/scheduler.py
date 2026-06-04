import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.ingestion.service import IngestionService

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


async def run_daily_cycle(company_id: int | None = None) -> dict:
    """Executa o ciclo diário de ingestão e extração em sessão independente."""
    async with SessionLocal() as session:
        service = IngestionService(session)
        return await service.run_scheduled_cycle(company_id=company_id)


def run_daily_cycle_sync(company_id: int | None = None) -> dict:
    """Adaptador síncrono para executar o ciclo diário no APScheduler."""
    return asyncio.run(run_daily_cycle(company_id=company_id))


def start_scheduler() -> BackgroundScheduler:
    """Inicia o scheduler diário de ingestão e extração quando inativo."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    settings = get_settings()
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(
        run_daily_cycle_sync,
        "cron",
        hour=settings.ingestion_schedule_hour,
        minute=settings.ingestion_schedule_minute,
        id="daily_ingestion_extraction",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler diário iniciado (horário=%02d:%02d, timezone=%s)",
        settings.ingestion_schedule_hour,
        settings.ingestion_schedule_minute,
        settings.scheduler_timezone,
    )
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    """Finaliza o scheduler global de ingestão quando ele está rodando."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler de ingestão finalizado")
    _scheduler = None


if __name__ == "__main__":
    result = run_daily_cycle_sync()
    print(result)
