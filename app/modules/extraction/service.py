import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.core.time import utc_now
from app.modules.documents.models import Document, DocumentStatus
from app.modules.extraction.chunking import Chunk, SemanticChunker
from app.modules.extraction.llm_client import build_llm_client
from app.modules.extraction.pdf_parser import PDFParser
from app.modules.lineage.models import DataLineage
from app.modules.metrics.catalog import canonical_metric_name, find_metric_definition
from app.modules.metrics.models import Metric
from app.modules.storage.service import build_object_storage

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self, session: AsyncSession):
        """Inicializa parser, chunker, cliente LLM e storage para extração."""
        self.session = session
        self.settings = get_settings()
        self.parser = PDFParser()
        self.chunker = SemanticChunker()
        self.llm = build_llm_client()
        self.storage = build_object_storage()

    async def process_document(self, document: Document, company_name: str) -> None:
        """Processa um documento individual e persiste métricas com linhagem."""
        parsed = self._parse_document(document)
        context = self._build_context(parsed.pages_text)
        payload = {
            "document_ref": str(document.id),
            "company": company_name,
            "original_url": document.original_url,
            "year": document.year,
            "quarter": document.quarter,
            "context": context,
        }
        batch = self.llm.extract_metrics_batch([payload])
        if not batch.documents:
            raise ValueError("LLM retornou lote vazio.")
        await self._persist_extraction(
            document=document,
            metrics=batch.documents[0].metrics,
        )

    async def process_pending_documents_batch(self, batch_size: int | None = None) -> dict:
        """Seleciona documentos pendentes e executa extração em lote."""
        size = batch_size or self.settings.extraction_batch_size
        stmt = (
            select(Document)
            .options(joinedload(Document.company))
            .where(Document.status == DocumentStatus.downloaded)
            .order_by(Document.collected_at.asc())
            .limit(size)
        )
        result = await self.session.scalars(stmt)
        docs = list(result.all())
        if not docs:
            return {"selected": 0, "processed": 0, "failed": 0}

        payloads: list[dict] = []
        by_ref: dict[str, tuple[Document, str]] = {}
        for doc in docs:
            company_name = doc.company.name if doc.company else "unknown"
            doc.status = DocumentStatus.processing
            self.session.add(doc)
            parsed = self._parse_document(doc)
            context = self._build_context(parsed.pages_text)
            doc_ref = str(doc.id)
            by_ref[doc_ref] = (doc, company_name)
            payloads.append(
                {
                    "document_ref": doc_ref,
                    "company": company_name,
                    "original_url": doc.original_url,
                    "year": doc.year,
                    "quarter": doc.quarter,
                    "context": context,
                }
            )
        await self.session.commit()

        processed = 0
        failed = 0
        try:
            extracted_batch = self.llm.extract_metrics_batch(payloads)
            returned_refs = {item.document_ref for item in extracted_batch.documents}

            for item in extracted_batch.documents:
                pair = by_ref.get(item.document_ref)
                if not pair:
                    continue
                doc, _ = pair
                await self._persist_extraction(
                    document=doc,
                    metrics=item.metrics,
                )
                processed += 1

            for ref, (doc, _) in by_ref.items():
                if ref in returned_refs:
                    continue
                doc.status = DocumentStatus.failed
                doc.error_message = "Documento não retornado no batch da LLM."
                self.session.add(doc)
                failed += 1
            await self.session.commit()
        except Exception as exc:
            for doc, _ in by_ref.values():
                doc.status = DocumentStatus.failed
                doc.error_message = str(exc)
                self.session.add(doc)
            await self.session.commit()
            raise
        return {"selected": len(docs), "processed": processed, "failed": failed}

    async def process_all_pending_documents(self, batch_size: int | None = None) -> dict:
        """Processa todos os documentos pendentes em lotes até esgotar a fila."""
        totals = {"batches": 0, "selected": 0, "processed": 0, "failed": 0}
        while True:
            result = await self.process_pending_documents_batch(batch_size=batch_size)
            if result["selected"] == 0:
                break
            totals["batches"] += 1
            totals["selected"] += result["selected"]
            totals["processed"] += result["processed"]
            totals["failed"] += result["failed"]
        return totals

    async def _persist_extraction(self, *, document: Document, metrics: list) -> None:
        """Persiste métricas normalizadas e seus registros de linhagem."""
        metric_rows: list[Metric] = []
        lineage_rows: list[DataLineage] = []
        for item in metrics:
            metric_name = canonical_metric_name(item.metric_name)
            definition = find_metric_definition(metric_name)
            unit, currency = _normalize_unit_and_currency(
                unit=item.unit,
                currency=item.currency,
                default_unit=definition.default_unit if definition else None,
                default_currency=definition.default_currency if definition else None,
            )
            metric = Metric(
                company_id=document.company_id,
                document_id=document.id,
                metric_name=metric_name,
                metric_category=item.metric_category
                or (definition.category if definition else None),
                period_year=item.period_year,
                period_quarter=item.period_quarter,
                value=item.value,
                unit=unit,
                currency=currency,
                source_page=item.source_page,
                source_excerpt=item.source_excerpt,
                confidence=item.confidence,
            )
            metric_rows.append(metric)

        self.session.add_all(metric_rows)
        await self.session.commit()
        for metric in metric_rows:
            await self.session.refresh(metric)
            lineage_rows.append(
                DataLineage(
                    metric_id=metric.id,
                    document_id=document.id,
                    original_url=document.original_url,
                    file_hash=document.file_hash or "",
                    source_page=metric.source_page,
                    source_excerpt=metric.source_excerpt,
                    extraction_model=_extraction_model_name(self.settings),
                    extraction_prompt_version=self.settings.extraction_prompt_version,
                    extracted_at=utc_now(),
                )
            )

        self.session.add_all(lineage_rows)
        document.status = DocumentStatus.processed
        document.processed_at = utc_now()
        document.error_message = None
        self.session.add(document)
        await self.session.commit()

    def _parse_document(self, document: Document):
        """Lê e parseia um documento a partir de path local ou storage URI."""
        if not document.local_path:
            raise ValueError("Documento sem local_path para leitura.")
        if _is_storage_uri(document.local_path):
            content = self.storage.read(document.local_path)
            return self.parser.parse_bytes(content)
        return self.parser.parse(document.local_path)

    def _build_context(self, pages_text: list[str]) -> str:
        """Monta o contexto enviado à LLM usando full scan ou chunking semântico."""
        full_text = "\n\n".join(
            [f"[Página {index}]\n{text}" for index, text in enumerate(pages_text, start=1)]
        )
        if len(full_text) <= self.settings.extraction_full_scan_max_chars:
            logger.info("Extração em modo full_scan (chars=%s)", len(full_text))
            return f"[MODO full_scan]\n{full_text}"

        chunks = self.chunker.build_chunks(pages_text)
        relevant_chunks = self.chunker.select_relevant_chunks(
            chunks,
            top_k=20,
            max_total_chars=self.settings.extraction_context_max_chars,
        )
        context = "\n\n".join(_format_chunk_for_llm(chunk) for chunk in relevant_chunks)
        logger.info(
            "Extração em modo chunking (chars=%s, chunks=%s)",
            len(context),
            len(relevant_chunks),
        )
        return f"[MODO semantic_chunking]\n{context}"


def _is_storage_uri(value: str) -> bool:
    """Indica se o caminho aponta para um backend de storage conhecido."""
    return value.startswith(("file://", "rustfs://", "s3://"))


def _format_chunk_for_llm(chunk: Chunk) -> str:
    """Formata um chunk com metadados de página, score, título e tags."""
    heading = f"\nTítulo/seção: {chunk.heading}" if chunk.heading else ""
    tags = f"\nTags semânticas: {', '.join(chunk.tags)}" if chunk.tags else ""
    return (
        f"[Página {chunk.page} | chunk {chunk.ordinal} | score {chunk.score}]"
        f"{heading}{tags}\n{chunk.text}"
    )


def _normalize_unit_and_currency(
    *,
    unit: str | None,
    currency: str | None,
    default_unit: str | None,
    default_currency: str | None,
) -> tuple[str | None, str | None]:
    """Normaliza unidade e moeda usando defaults do catálogo canônico."""
    normalized_currency = currency
    normalized_unit = unit
    if unit and unit.upper() in {"BRL", "USD"}:
        normalized_currency = normalized_currency or unit.upper()
        normalized_unit = default_unit
    normalized_unit = normalized_unit or default_unit
    if normalized_currency is None and normalized_unit != "%":
        normalized_currency = default_currency
    return normalized_unit, normalized_currency


def _extraction_model_name(settings) -> str:
    """Resolve o nome do modelo usado na linhagem conforme o provider."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return settings.openai_model
    if provider == "ollama":
        return settings.ollama_model
    return provider
