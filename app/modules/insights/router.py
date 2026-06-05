from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.companies.repository import CompanyRepository
from app.modules.insights.repository import DocumentInsightRepository
from app.modules.insights.schemas import DocumentInsightRead
from app.modules.insights.service import DocumentInsightService

router = APIRouter(prefix="/api/insights", tags=["Insights"])

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_service(session: SessionDep) -> DocumentInsightService:
    """Monta o serviço de insights para injeção de dependência."""
    return DocumentInsightService(
        DocumentInsightRepository(session),
        CompanyRepository(session),
    )


ServiceDep = Annotated[DocumentInsightService, Depends(get_service)]


@router.get(
    "",
    response_model=list[DocumentInsightRead],
    summary="Listar insights documentais",
    description="Lista fatos, metas, ações e riscos extraídos dos documentos.",
)
async def list_insights(
    service: ServiceDep,
    empresa: str | None = Query(default=None, description="Nome ou ticker da empresa."),
    document_id: int | None = Query(default=None, description="ID do documento de origem."),
    tipo: str | None = Query(default=None, description="Tipo do insight, como meta ou risco."),
    topico: str | None = Query(default=None, description="Tópico canônico do insight."),
    ano: int | None = Query(default=None, description="Ano de referência."),
):
    """Endpoint para listar insights extraídos dos documentos."""
    return await service.list_insights(
        empresa=empresa,
        document_id=document_id,
        insight_type=tipo,
        topic=topico,
        ano=ano,
    )
