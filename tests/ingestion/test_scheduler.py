import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.ingestion import scheduler as scheduler_module


class _FakeSessionLocal:
    def __init__(self):
        """Inicializa sessionmaker fake com sessão sentinela."""
        self.session = object()

    async def __aenter__(self):
        """Entrega sessão fake no contexto assíncrono."""
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        """Sai do contexto sem suprimir exceções."""
        return None


class _FakeIngestionService:
    def __init__(self, session):
        """Inicializa serviço fake preservando a sessão recebida."""
        self.session = session

    async def run_scheduled_cycle(self, company_id=None):
        """Retorna o company_id para validar repasse de argumento."""
        return {"company_id": company_id}


class _FakeScheduler:
    def __init__(self, timezone):
        """Inicializa scheduler fake com timezone e lista de jobs."""
        self.timezone = timezone
        self.running = False
        self.jobs = []
        self.shutdown_wait = None

    def add_job(self, *args, **kwargs):
        """Registra job agendado."""
        self.jobs.append((args, kwargs))

    def start(self):
        """Marca scheduler como ativo."""
        self.running = True

    def shutdown(self, wait):
        """Registra shutdown e marca scheduler como inativo."""
        self.shutdown_wait = wait
        self.running = False


@pytest.mark.asyncio
async def test_run_daily_cycle_usa_sessionlocal_e_service(monkeypatch):
    """Valida uso de SessionLocal e IngestionService no ciclo diário."""
    monkeypatch.setattr(scheduler_module, "SessionLocal", _FakeSessionLocal)
    monkeypatch.setattr(scheduler_module, "IngestionService", _FakeIngestionService)

    assert await scheduler_module.run_daily_cycle(company_id=42) == {"company_id": 42}


def test_run_daily_cycle_sync(monkeypatch):
    """Valida wrapper síncrono do ciclo diário."""
    async def fake_run_daily_cycle(company_id=None):
        """Retorna company_id para validar wrapper."""
        return {"company_id": company_id}

    monkeypatch.setattr(scheduler_module, "run_daily_cycle", fake_run_daily_cycle)

    assert scheduler_module.run_daily_cycle_sync(company_id=7) == {"company_id": 7}


def test_start_scheduler_reusa_ativo_e_stop_desliga(monkeypatch):
    """Garante reuso de scheduler ativo e desligamento correto."""
    monkeypatch.setattr(scheduler_module, "_scheduler", None)
    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", _FakeScheduler)
    monkeypatch.setattr(
        scheduler_module,
        "get_settings",
        lambda: SimpleNamespace(
            scheduler_timezone="America/Sao_Paulo",
            ingestion_schedule_hour=2,
            ingestion_schedule_minute=0,
        ),
    )

    created = scheduler_module.start_scheduler()
    reused = scheduler_module.start_scheduler()

    assert created is reused
    assert created.running is True
    assert created.timezone == "America/Sao_Paulo"
    assert created.jobs[0][1]["hour"] == 2
    assert created.jobs[0][1]["minute"] == 0
    assert created.jobs[0][1]["id"] == "daily_ingestion_extraction"

    scheduler_module.stop_scheduler()

    assert created.shutdown_wait is False
    assert scheduler_module._scheduler is None


def test_stop_scheduler_sem_scheduler_ativo(monkeypatch):
    """Garante que stop sem scheduler ativo não falha."""
    monkeypatch.setattr(scheduler_module, "_scheduler", None)

    scheduler_module.stop_scheduler()

    assert scheduler_module._scheduler is None


def test_scheduler_main_executa_ingestao(monkeypatch, capsys):
    """Valida execução do módulo scheduler como script."""
    import app.core.database as database_module
    import app.modules.ingestion.service as ingestion_service_module

    monkeypatch.setattr(database_module, "SessionLocal", _FakeSessionLocal)
    monkeypatch.setattr(ingestion_service_module, "IngestionService", _FakeIngestionService)

    runpy.run_path(Path(scheduler_module.__file__), run_name="__main__")

    assert "{'company_id': None}" in capsys.readouterr().out
