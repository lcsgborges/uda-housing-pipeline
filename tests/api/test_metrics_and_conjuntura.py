import pytest

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.metrics.models import Metric


@pytest.mark.asyncio
async def test_consulta_metricas(client, db_session):
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br", is_active=True)
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Prévia Operacional 3T25",
        original_url="https://ri.mrv.com.br/previa_3t25.pdf",
        local_path="/tmp/doc.pdf",
        file_hash="abc",
        year=2025,
        quarter=3,
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
        period_quarter=3,
        value=123.0,
        unit="R$",
        currency="BRL",
        source_page=4,
        source_excerpt="Vendas líquidas totalizaram...",
        confidence=0.92,
    )
    db_session.add(metric)
    await db_session.commit()

    resp_metrics = client.get("/api/metrics")
    assert resp_metrics.status_code == 200
    assert len(resp_metrics.json()) == 1

    resp_filtered = client.get(
        "/api/metrics",
        params={
            "empresa": "MRV",
            "ano": 2025,
            "trimestre": 3,
            "metrica": "vendas_líquidas",
        },
    )
    assert resp_filtered.status_code == 200
    assert len(resp_filtered.json()) == 1

    resp_empty = client.get("/api/metrics", params={"empresa": "MRV", "ano": 2024})
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []

    resp_conjuntura = client.get(
        "/api/conjuntura",
        params={"empresa": "MRV", "ano": 2025, "trimestre": 3},
    )
    resp_conjuntura_ticker = client.get(
        "/api/conjuntura",
        params={"empresa": "MRVE3", "ano": 2025, "trimestre": 3},
    )
    resp_metric = client.get("/api/metrics/1")
    resp_metric_missing = client.get("/api/metrics/999")
    assert resp_conjuntura.status_code == 200
    payload = resp_conjuntura.json()
    assert payload["empresa"] == "MRV"
    assert payload["metricas"][0]["nome"] == "vendas_liquidas"
    assert resp_conjuntura_ticker.status_code == 200
    assert resp_metric.status_code == 200
    assert resp_metric_missing.status_code == 404


@pytest.mark.asyncio
async def test_consulta_empresa_ignora_acentos(client, db_session):
    company = Company(
        name="São José",
        ticker="SJOS3",
        ri_url="https://ri.saojose.com.br",
        is_active=True,
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Prévia Operacional 2T25",
        original_url="https://ri.saojose.com.br/previa_2t25.pdf",
        local_path="/tmp/doc.pdf",
        file_hash="saojose",
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
        metric_name="lancamentos",
        metric_category="operacional",
        period_year=2025,
        period_quarter=2,
        value=42.0,
        unit="unidades",
        currency=None,
        source_page=1,
        source_excerpt="Lançamentos no trimestre.",
        confidence=0.91,
    )
    db_session.add(metric)
    await db_session.commit()

    resp_sem_acento = client.get(
        "/api/metrics",
        params={"empresa": "Sao Jose", "ano": 2025, "trimestre": 2},
    )
    resp_com_acento = client.get(
        "/api/conjuntura",
        params={"empresa": "são josé", "ano": 2025, "trimestre": 2},
    )

    assert resp_sem_acento.status_code == 200
    assert len(resp_sem_acento.json()) == 1
    assert resp_com_acento.status_code == 200
    assert resp_com_acento.json()["empresa"] == "São José"
