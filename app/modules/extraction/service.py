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
from app.modules.insights.models import DocumentInsight
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
            "title": document.title,
            "document_type": document.document_type,
            "original_url": document.original_url,
            "year": document.year,
            "quarter": document.quarter,
            "context": context,
        }
        batch = self.llm.extract_metrics_batch([payload])
        batch_item = next(
            (item for item in batch.documents if item.document_ref == payload["document_ref"]),
            None,
        )
        metrics = batch_item.metrics if batch_item else None
        insights = batch_item.insights if batch_item else None
        if not metrics and not insights:
            retry_response, retry_error = self._extract_single_document(payload)
            metrics = retry_response.metrics if retry_response else None
            insights = retry_response.insights if retry_response else None
            if retry_error:
                logger.warning(
                    "Retry individual falhou para documento %s: %s",
                    document.id,
                    retry_error,
                )
        if not metrics and not insights:
            failure_message = "Nenhuma métrica ou insight extraído do documento."
            if retry_error:
                failure_message = f"{failure_message} Retry individual falhou: {retry_error}"
            _mark_document_failed(document, failure_message)
            self.session.add(document)
            await self.session.commit()
            raise ValueError(failure_message)
        await self._persist_extraction(
            document=document,
            metrics=metrics,
            insights=insights,
        )

    async def process_pending_documents_batch(self, batch_size: int | None = None) -> dict:
        """Seleciona documentos pendentes e executa extração em lote."""
        size = batch_size or self.settings.extraction_batch_size
        stmt = (
            select(Document)
            .options(joinedload(Document.company))
            .where(Document.status == DocumentStatus.classified_useful)
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
            doc.error_message = None
            self.session.add(doc)
            parsed = self._parse_document(doc)
            context = self._build_context(parsed.pages_text)
            doc_ref = str(doc.id)
            by_ref[doc_ref] = (doc, company_name)
            payloads.append(
                {
                    "document_ref": doc_ref,
                    "company": company_name,
                    "title": doc.title,
                    "document_type": doc.document_type,
                    "original_url": doc.original_url,
                    "year": doc.year,
                    "quarter": doc.quarter,
                    "context": context,
                }
            )
        await self.session.commit()

        processed = 0
        failed = 0
        processed_refs: set[str] = set()
        try:
            extracted_batch = self.llm.extract_metrics_batch(payloads)
            returned_by_ref = {item.document_ref: item for item in extracted_batch.documents}
            payload_by_ref = {payload["document_ref"]: payload for payload in payloads}

            for ref, (doc, _) in by_ref.items():
                item = returned_by_ref.get(ref)
                metrics = item.metrics if item else None
                insights = item.insights if item else None
                failure_message = None

                if not metrics and not insights:
                    retry_response, retry_error = self._extract_single_document(payload_by_ref[ref])
                    metrics = retry_response.metrics if retry_response else None
                    insights = retry_response.insights if retry_response else None
                    if not metrics and not insights:
                        if item is None:
                            failure_message = "Documento não retornado no batch da LLM."
                        else:
                            failure_message = "Nenhuma métrica ou insight extraído do documento."
                        if retry_error:
                            failure_message = (
                                f"{failure_message} Retry individual falhou: {retry_error}"
                            )

                if failure_message:
                    _mark_document_failed(doc, failure_message)
                    self.session.add(doc)
                    failed += 1
                    continue
                try:
                    await self._persist_extraction(
                        document=doc,
                        metrics=metrics,
                        insights=insights,
                    )
                except Exception as exc:
                    _mark_document_failed(doc, str(exc))
                    self.session.add(doc)
                    await self.session.commit()
                    failed += 1
                    continue
                processed += 1
                processed_refs.add(ref)
            await self.session.commit()
        except Exception as exc:
            for ref, (doc, _) in by_ref.items():
                if ref in processed_refs:
                    continue
                _mark_document_failed(doc, str(exc))
                self.session.add(doc)
                failed += 1
            await self.session.commit()
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

    async def _persist_extraction(
        self,
        *,
        document: Document,
        metrics: list | None,
        insights: list | None = None,
    ) -> None:
        """Persiste métricas normalizadas, insights e registros de linhagem."""
        metrics = metrics or []
        insights = insights or []
        if not metrics and not insights:
            raise ValueError("Nenhuma métrica ou insight extraído do documento.")

        metric_rows: list[Metric] = []
        lineage_rows: list[DataLineage] = []
        for item in metrics:
            if item.value is None:
                continue
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
                period_label=item.period_label,
                raw_label=item.raw_label,
                dimension=item.dimension,
                value=item.value,
                unit=unit,
                currency=currency,
                source_page=item.source_page,
                source_excerpt=item.source_excerpt,
                confidence=item.confidence,
            )
            metric_rows.append(metric)

        insight_rows = [
            DocumentInsight(
                company_id=document.company_id,
                document_id=document.id,
                insight_type=item.insight_type,
                topic=item.topic,
                summary=item.summary,
                value_text=item.value_text,
                period_year=item.period_year,
                period_quarter=item.period_quarter,
                source_page=item.source_page,
                source_excerpt=item.source_excerpt,
                confidence=item.confidence,
            )
            for item in insights
        ]

        if not metric_rows and not insight_rows:
            message = "Nenhuma métrica com valor ou insight extraído do documento."
            _mark_document_failed(document, message)
            self.session.add(document)
            await self.session.commit()
            raise ValueError(message)

        self.session.add_all(metric_rows)
        self.session.add_all(insight_rows)
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

    def _extract_single_document(self, payload: dict):
        """Tenta reprocessar um documento individualmente após falha no batch."""
        try:
            extracted = self.llm.extract_metrics(
                company=payload["company"],
                title=payload.get("title"),
                document_type=payload.get("document_type"),
                original_url=payload["original_url"],
                context=payload["context"],
                year=payload.get("year"),
                quarter=payload.get("quarter"),
            )
        except Exception as exc:
            return None, str(exc)
        return extracted, None

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


def _mark_document_failed(document: Document, message: str) -> None:
    """Atualiza um documento para falha mantendo a mensagem auditável."""
    document.status = DocumentStatus.failed
    document.processed_at = None
    document.error_message = message


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
