import pytest

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.metrics.models import Metric
from app.modules.metrics.repository import MetricRepository
from app.modules.metrics.service import _catalog_category, _quality_level


@pytest.mark.asyncio
async def test_metric_repository_create_many_e_list_all(db_session):
    """Valida criação em lote e ordenação de listagem de métricas."""
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Prévia 3T25",
        original_url="https://ri.mrv.com.br/previa.pdf",
        local_path="/tmp/previa.pdf",
        file_hash="hash_metric_repository",
        year=2025,
        quarter=3,
        document_type="previa_operacional",
        status=DocumentStatus.processed,
        collected_at=utc_now(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    repository = MetricRepository(db_session)
    created = await repository.create_many(
        [
            Metric(
                company_id=company.id,
                document_id=document.id,
                metric_name="vendas_liquidas",
                period_year=2025,
                period_quarter=3,
                value=100.0,
                confidence=0.9,
            ),
            Metric(
                company_id=company.id,
                document_id=document.id,
                metric_name="lucro_liquido",
                period_year=2025,
                period_quarter=3,
                value=20.0,
                confidence=0.8,
            ),
        ]
    )
    listed = await repository.list_all()

    assert [metric.id for metric in created] == [1, 2]
    assert [metric.metric_name for metric in listed] == ["lucro_liquido", "vendas_liquidas"]


def test_metric_service_quality_level_e_categoria_de_catalogo():
    """Cobre níveis de qualidade e categoria obtida do catálogo."""
    assert _quality_level(85) == "alta"
    assert _quality_level(65) == "media"
    assert _quality_level(64) == "baixa"
    assert _catalog_category("vendas_liquidas") == "operacional"
    assert _catalog_category("metrica_fora_catalogo") is None
