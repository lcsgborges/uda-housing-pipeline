import asyncio
from datetime import datetime

from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.metrics.models import Metric


def test_consulta_metricas(client, db_session):
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br", is_active=True)
    db_session.add(company)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(company))

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
        collected_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
    )
    db_session.add(document)
    asyncio.run(db_session.commit())
    asyncio.run(db_session.refresh(document))

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
    asyncio.run(db_session.commit())

    resp_metrics = client.get("/api/metrics")
    assert resp_metrics.status_code == 200
    assert len(resp_metrics.json()) == 1

    resp_filtered = client.get(
        "/api/metrics",
        params={
            "empresa": "MRV",
            "ano": 2025,
            "trimestre": 3,
            "metrica": "vendas_liquidas",
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
    assert resp_conjuntura.status_code == 200
    payload = resp_conjuntura.json()
    assert payload["empresa"] == "MRV"
    assert payload["metricas"][0]["nome"] == "vendas_liquidas"
