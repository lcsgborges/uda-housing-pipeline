import pytest

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.lineage.models import DataLineage
from app.modules.lineage.repository import DataLineageRepository
from app.modules.lineage.schemas import DataLineageRead
from app.modules.lineage.service import DataLineageService
from app.modules.metrics.models import Metric


@pytest.mark.asyncio
async def test_lineage_repository_create_many_e_schema(db_session):
    company = Company(name="Plano & Plano", ticker="PLPL3", ri_url="https://ri.planoeplano.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Resultado 3T25",
        original_url="https://example.com/doc.pdf",
        local_path="/tmp/doc.pdf",
        file_hash="hash_lineage",
        year=2025,
        quarter=3,
        document_type="resultado_trimestral",
        status=DocumentStatus.processed,
        collected_at=utc_now(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    metric = Metric(
        company_id=company.id,
        document_id=document.id,
        metric_name="vendas_liquidas",
        value=10.0,
        confidence=0.9,
    )
    db_session.add(metric)
    await db_session.commit()
    await db_session.refresh(metric)

    repository = DataLineageRepository(db_session)
    service = DataLineageService(repository)
    rows = await service.repository.create_many(
        [
            DataLineage(
                metric_id=metric.id,
                document_id=document.id,
                original_url=document.original_url,
                file_hash=document.file_hash,
                source_page=1,
                source_excerpt="Vendas líquidas 10",
                extraction_model="llama3.1",
                extraction_prompt_version="v1",
                extracted_at=utc_now(),
            )
        ]
    )

    schema = DataLineageRead.model_validate(rows[0])

    assert rows[0].id is not None
    assert schema.original_url == document.original_url
    assert schema.metric_id == metric.id
