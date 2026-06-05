from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app import main as main_module
from app.core.database import get_db_session


@pytest.mark.asyncio
async def test_get_db_session_yields_async_session():
    """Garante que a dependência de banco entrega uma AsyncSession."""
    session_generator = get_db_session()
    session = await anext(session_generator)

    try:
        assert isinstance(session, AsyncSession)
    finally:
        await session_generator.aclose()


@pytest.mark.asyncio
async def test_lifespan_inicia_scheduler_quando_habilitado(monkeypatch):
    """Valida start e stop do scheduler quando a configuração habilita ingestão."""
    calls = []

    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(enable_ingestion_scheduler=True),
    )
    monkeypatch.setattr(main_module, "start_scheduler", lambda: calls.append("start"))
    monkeypatch.setattr(main_module, "stop_scheduler", lambda: calls.append("stop"))

    async with main_module.lifespan(FastAPI()):
        assert calls == ["start"]

    assert calls == ["start", "stop"]


def test_health_endpoint(client):
    """Valida o endpoint básico de saúde da API."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
