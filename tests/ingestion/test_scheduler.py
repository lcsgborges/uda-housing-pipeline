import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.ingestion import scheduler as scheduler_module


class _FakeSessionLocal:
    def __init__(self):
        self.session = object()

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _FakeIngestionService:
    def __init__(self, session):
        self.session = session

    async def run(self, company_id=None):
        return {"company_id": company_id}


class _FakeScheduler:
    def __init__(self, timezone):
        self.timezone = timezone
        self.running = False
        self.jobs = []
        self.shutdown_wait = None

    def add_job(self, *args, **kwargs):
        self.jobs.append((args, kwargs))

    def start(self):
        self.running = True

    def shutdown(self, wait):
        self.shutdown_wait = wait
        self.running = False


@pytest.mark.asyncio
async def test_run_ingestion_usa_sessionlocal_e_service(monkeypatch):
    monkeypatch.setattr(scheduler_module, "SessionLocal", _FakeSessionLocal)
    monkeypatch.setattr(scheduler_module, "IngestionService", _FakeIngestionService)

    assert await scheduler_module.run_ingestion(company_id=42) == {"company_id": 42}


def test_run_ingestion_sync(monkeypatch):
    async def fake_run_ingestion(company_id=None):
        return {"company_id": company_id}

    monkeypatch.setattr(scheduler_module, "run_ingestion", fake_run_ingestion)

    assert scheduler_module.run_ingestion_sync(company_id=7) == {"company_id": 7}


def test_start_scheduler_reusa_ativo_e_stop_desliga(monkeypatch):
    monkeypatch.setattr(scheduler_module, "_scheduler", None)
    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", _FakeScheduler)
    monkeypatch.setattr(
        scheduler_module,
        "get_settings",
        lambda: SimpleNamespace(ingestion_poll_interval_minutes=15),
    )

    created = scheduler_module.start_scheduler()
    reused = scheduler_module.start_scheduler()

    assert created is reused
    assert created.running is True
    assert created.jobs[0][1]["minutes"] == 15
    assert created.jobs[0][1]["id"] == "ingestion_polling"

    scheduler_module.stop_scheduler()

    assert created.shutdown_wait is False
    assert scheduler_module._scheduler is None


def test_stop_scheduler_sem_scheduler_ativo(monkeypatch):
    monkeypatch.setattr(scheduler_module, "_scheduler", None)

    scheduler_module.stop_scheduler()

    assert scheduler_module._scheduler is None


def test_scheduler_main_executa_ingestao(monkeypatch, capsys):
    import app.core.database as database_module
    import app.modules.ingestion.service as ingestion_service_module

    monkeypatch.setattr(database_module, "SessionLocal", _FakeSessionLocal)
    monkeypatch.setattr(ingestion_service_module, "IngestionService", _FakeIngestionService)

    runpy.run_path(Path(scheduler_module.__file__), run_name="__main__")

    assert "{'company_id': None}" in capsys.readouterr().out
