import pytest
from fastapi import HTTPException

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.companies.repository import CompanyRepository
from app.modules.documents.models import Document, DocumentStatus
from app.modules.metrics.models import Metric
from app.modules.metrics.repository import MetricRepository
from app.modules.metrics.service import MetricService


@pytest.mark.asyncio
async def test_metric_repository_query_and_conjuntura_branches(db_session):
    """Valida filtros do repositório e consulta de conjuntura."""
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Prévia 3T25",
        original_url="https://ri.mrv.com.br/previa.pdf",
        local_path="/tmp/previa.pdf",
        file_hash="hash_metric_branches",
        year=2025,
        quarter=3,
        document_type="previa_operacional",
        status=DocumentStatus.processed,
        collected_at=utc_now(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    first_metric = Metric(
        company_id=company.id,
        document_id=document.id,
        metric_name="vendas_liquidas",
        metric_category="operacional",
        period_year=2025,
        period_quarter=3,
        value=100.0,
        confidence=0.9,
    )
    second_metric = Metric(
        company_id=company.id,
        document_id=document.id,
        metric_name="lucro_liquido",
        metric_category="financeira",
        period_year=2025,
        period_quarter=3,
        value=20.0,
        confidence=0.8,
    )
    db_session.add_all([first_metric, second_metric])
    await db_session.commit()
    await db_session.refresh(first_metric)
    await db_session.refresh(second_metric)

    repository = MetricRepository(db_session)

    all_metrics = await repository.query()
    filtered_metrics = await repository.query(
        company_id=company.id,
        year=2025,
        quarter=3,
        metric_name="vendas_liquidas",
    )
    conjunctura_metrics = await repository.query_conjuntura(company.id, 2025, 3)

    assert [metric.id for metric in all_metrics] == [second_metric.id, first_metric.id]
    assert [metric.id for metric in filtered_metrics] == [first_metric.id]
    assert [metric.metric_name for metric in conjunctura_metrics] == [
        "lucro_liquido",
        "vendas_liquidas",
    ]
    assert await repository.get_by_id(first_metric.id) is not None


@pytest.mark.asyncio
async def test_metric_service_lookup_and_not_found_branches(db_session):
    """Cobre busca por empresa, Gold, métrica encontrada e erros 404."""
    company = Company(name="São José", ticker="SJOS3", ri_url="https://ri.saojose.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Prévia 2T25",
        original_url="https://ri.saojose.com.br/previa.pdf",
        local_path="/tmp/previa-2t25.pdf",
        file_hash="hash_metric_service",
        year=2025,
        quarter=2,
        document_type="previa_operacional",
        status=DocumentStatus.processed,
        collected_at=utc_now(),
        processed_at=utc_now(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    metric = Metric(
        company_id=company.id,
        document_id=document.id,
        metric_name="vendas_liquidas",
        metric_category="operacional",
        period_year=2025,
        period_quarter=2,
        value=42.0,
        unit="unidades",
        confidence=0.91,
        source_page=1,
        source_excerpt="Vendas líquidas no trimestre.",
    )
    alt_metric = Metric(
        company_id=company.id,
        document_id=document.id,
        metric_name="vendas_liquidas",
        metric_category="operacional",
        period_year=2025,
        period_quarter=2,
        value=None,
        unit="unidades",
        confidence=0.95,
        source_page=1,
        source_excerpt="Versão menos completa.",
    )
    db_session.add_all([metric, alt_metric])
    await db_session.commit()
    await db_session.refresh(metric)
    await db_session.refresh(alt_metric)

    service = MetricService(MetricRepository(db_session), CompanyRepository(db_session))

    listed = await service.list_all(
        empresa="sao jose",
        ano=2025,
        trimestre=2,
        metrica="vendas_líquidas",
    )
    conjuntura = await service.conjuntura(empresa="SJOS3", ano=2025, trimestre=2)
    found_metric = await service.get_or_404(metric.id)

    assert listed == [alt_metric, metric]
    assert conjuntura.empresa == "São José"
    assert len(conjuntura.metricas) == 1
    assert conjuntura.metricas[0].nome == "vendas_liquidas"
    assert conjuntura.metricas[0].qualidade.camada == "gold"
    assert found_metric.id == metric.id

    with pytest.raises(HTTPException) as excinfo:
        await service.list_all(empresa="Empresa Inexistente")
    assert excinfo.value.status_code == 404

    with pytest.raises(HTTPException) as excinfo:
        await service.get_or_404(999)
    assert excinfo.value.status_code == 404
