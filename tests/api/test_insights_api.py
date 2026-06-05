import pytest

from app.core.time import utc_now
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.insights.models import DocumentInsight


@pytest.mark.asyncio
async def test_lista_insights_com_filtros(client, db_session):
    company = Company(name="MRV", ticker="MRVE3", ri_url="https://ri.mrv.com.br")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    document = Document(
        company_id=company.id,
        title="Relatório de Sustentabilidade",
        original_url="https://example.com/sust.pdf",
        local_path="/tmp/sust.pdf",
        file_hash="hash_insights_api",
        year=2025,
        document_type="relatorio_sustentabilidade",
        status=DocumentStatus.processed,
        collected_at=utc_now(),
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    db_session.add(
        DocumentInsight(
            company_id=company.id,
            document_id=document.id,
            insight_type="meta",
            topic="emissoes_gee",
            summary="Meta de redução de emissões por unidade produzida.",
            value_text="5% no ciclo 2025",
            period_year=2025,
            source_page=55,
            source_excerpt="redução em 5% das emissões.",
            confidence=0.92,
        )
    )
    await db_session.commit()

    response = client.get(
        "/api/insights",
        params={"empresa": "MRVE3", "tipo": "meta", "ano": 2025},
    )
    empty = client.get("/api/insights", params={"empresa": "NAO_EXISTE"})

    assert response.status_code == 200
    assert response.json()[0]["topic"] == "emissoes_gee"
    assert response.json()[0]["value_text"] == "5% no ciclo 2025"
    assert empty.status_code == 200
    assert empty.json() == []
