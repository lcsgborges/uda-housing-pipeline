import asyncio
import atexit
import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from testcontainers.postgres import PostgresContainer

postgres = PostgresContainer(
    os.getenv("TEST_POSTGRES_IMAGE", "postgres:16-alpine"),
    driver="asyncpg",
)
postgres.start()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = postgres.get_connection_url()
os.environ["STORAGE_BACKEND"] = "local"
os.environ["DOCUMENTS_DIR"] = "/tmp/uda-test-documents"
os.environ["LLM_PROVIDER"] = "ollama"
_postgres_stopped = False


def stop_postgres() -> None:
    global _postgres_stopped
    if not _postgres_stopped:
        postgres.stop()
        _postgres_stopped = True


atexit.register(stop_postgres)

from app.core.database import Base, engine, get_db_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models_registry import (  # noqa: E402
    Company,
    DataLineage,
    Document,
    DocumentInsight,
    Metric,
)

_ = (Company, Document, Metric, DataLineage, DocumentInsight)

TestingSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def postgres_container() -> Generator[PostgresContainer, None, None]:
    async def _prepare_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_prepare_schema())
    yield postgres
    asyncio.run(engine.dispose())
    stop_postgres()


@pytest.fixture(autouse=True)
def clean_db() -> Generator[None, None, None]:
    yield

    async def _clean() -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    TRUNCATE TABLE
                        data_lineage,
                        document_insights,
                        metrics,
                        documents,
                        companies
                    RESTART IDENTITY CASCADE
                    """
                )
            )

    asyncio.run(_clean())


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
