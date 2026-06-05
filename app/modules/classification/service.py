from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.core.time import utc_now
from app.modules.classification.schemas import DocumentClassification
from app.modules.documents.models import Document, DocumentStatus
from app.modules.extraction.chunking import Chunk, SemanticChunker
from app.modules.extraction.llm_client import build_llm_client
from app.modules.extraction.pdf_parser import ParsedPDF, PDFParser
from app.modules.storage.service import build_object_storage


class ClassificationService:
    def __init__(self, session: AsyncSession):
        """Inicializa parser, chunker, cliente LLM barato e storage."""
        self.session = session
        self.settings = get_settings()
        self.parser = PDFParser()
        self.chunker = SemanticChunker()
        self.llm = build_llm_client()
        self.storage = build_object_storage()

    async def classify_document(
        self,
        document: Document,
        company_name: str,
    ) -> DocumentClassification:
        """Classifica um documento e persiste a decisão no próprio registro."""
        document.status = DocumentStatus.classifying
        document.error_message = None
        self.session.add(document)
        await self.session.commit()

        try:
            parsed = self._parse_document(document)
            if _needs_ocr(parsed):
                classification = _ocr_classification(document)
            else:
                classification = self.llm.classify_document(
                    company=company_name,
                    title=document.title,
                    original_url=document.original_url,
                    document_type=document.document_type,
                    year=document.year,
                    quarter=document.quarter,
                    pages_count=parsed.pages_count,
                    text_chars=len(parsed.full_text),
                    context=self._build_context(parsed),
                )
            _apply_classification(
                document,
                classification,
                model=_classification_model_name(self.settings),
            )
            self.session.add(document)
            await self.session.commit()
            return classification
        except Exception as exc:
            document.status = DocumentStatus.failed
            document.error_message = f"Falha na classificação: {exc}"
            self.session.add(document)
            await self.session.commit()
            raise

    async def process_pending_documents_batch(self, batch_size: int | None = None) -> dict:
        """Classifica documentos baixados que ainda não passaram pelo filtro barato."""
        size = batch_size or self.settings.classification_batch_size
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
            return {"selected": 0, "useful": 0, "ignored": 0, "needs_ocr": 0, "failed": 0}

        totals = {"selected": len(docs), "useful": 0, "ignored": 0, "needs_ocr": 0, "failed": 0}
        for doc in docs:
            company_name = doc.company.name if doc.company else "unknown"
            try:
                await self.classify_document(doc, company_name=company_name)
            except Exception:
                totals["failed"] += 1
                continue
            if doc.status == DocumentStatus.classified_useful:
                totals["useful"] += 1
            elif doc.status == DocumentStatus.needs_ocr:
                totals["needs_ocr"] += 1
            elif doc.status == DocumentStatus.ignored_not_relevant:
                totals["ignored"] += 1
        return totals

    async def process_all_pending_documents(self, batch_size: int | None = None) -> dict:
        """Classifica todos os documentos pendentes em lotes até esgotar a fila."""
        totals = {
            "batches": 0,
            "selected": 0,
            "useful": 0,
            "ignored": 0,
            "needs_ocr": 0,
            "failed": 0,
        }
        while True:
            result = await self.process_pending_documents_batch(batch_size=batch_size)
            if result["selected"] == 0:
                break
            totals["batches"] += 1
            for key in ("selected", "useful", "ignored", "needs_ocr", "failed"):
                totals[key] += result[key]
        return totals

    def _parse_document(self, document: Document) -> ParsedPDF:
        """Lê e parseia um documento a partir de path local ou storage URI."""
        if not document.local_path:
            raise ValueError("Documento sem local_path para leitura.")
        if document.local_path.startswith(("file://", "rustfs://", "s3://")):
            return self.parser.parse_bytes(self.storage.read(document.local_path))
        return self.parser.parse(document.local_path)

    def _build_context(self, parsed: ParsedPDF) -> str:
        """Monta uma amostra barata: início do PDF mais chunks semanticamente fortes."""
        first_pages = [
            _format_page_for_classification(index, text)
            for index, text in enumerate(
                parsed.pages_text[: self.settings.classification_sample_pages],
                start=1,
            )
            if text.strip()
        ]
        chunks = self.chunker.select_relevant_chunks(
            self.chunker.build_chunks(parsed.pages_text),
            top_k=12,
            max_total_chars=self.settings.classification_context_max_chars,
        )
        candidates = [*first_pages, *[_format_chunk_for_classification(chunk) for chunk in chunks]]
        return _fit_context(candidates, self.settings.classification_context_max_chars)


def _apply_classification(
    document: Document,
    classification: DocumentClassification,
    *,
    model: str,
) -> None:
    """Aplica a classificação estruturada aos campos persistidos do documento."""
    document.classification_is_useful = classification.is_useful
    document.classification_confidence = classification.confidence
    document.classification_reason = classification.reason
    document.classification_model = model
    document.detected_domains = list(classification.domains)
    document.extraction_strategy = classification.extraction_strategy
    document.classified_at = utc_now()
    document.document_type = classification.document_type
    document.year = classification.year or document.year
    document.quarter = classification.quarter or document.quarter

    if classification.extraction_strategy == "needs_ocr":
        document.status = DocumentStatus.needs_ocr
        document.error_message = classification.reason
    elif not classification.is_useful or classification.extraction_strategy == "ignore":
        document.status = DocumentStatus.ignored_not_relevant
        document.error_message = classification.reason
    else:
        document.status = DocumentStatus.classified_useful
        document.error_message = None


def _needs_ocr(parsed: ParsedPDF) -> bool:
    """Detecta PDFs com texto insuficiente para classificação confiável."""
    text_chars = len(parsed.full_text.strip())
    if parsed.pages_count == 0:
        return True
    if text_chars < 50:
        return True
    return parsed.pages_count >= 3 and text_chars < parsed.pages_count * 20


def _ocr_classification(document: Document) -> DocumentClassification:
    """Cria classificação determinística para PDFs sem texto extraível."""
    return DocumentClassification(
        is_useful=False,
        document_type=document.document_type or "outro",
        domains=[],
        year=document.year,
        quarter=document.quarter,
        extraction_strategy="needs_ocr",
        reason="Texto extraído insuficiente para classificar; possível PDF escaneado.",
        confidence=0.95,
    )


def _format_page_for_classification(page: int, text: str) -> str:
    """Formata página inicial para a amostra do classificador."""
    return f"[Página inicial {page}]\n{text.strip()}"


def _format_chunk_for_classification(chunk: Chunk) -> str:
    """Formata chunk ranqueado para a amostra do classificador."""
    heading = f"\nTítulo/seção: {chunk.heading}" if chunk.heading else ""
    tags = f"\nTags: {', '.join(chunk.tags)}" if chunk.tags else ""
    return f"[Página {chunk.page} | score {chunk.score}]{heading}{tags}\n{chunk.text.strip()}"


def _fit_context(candidates: list[str], max_chars: int) -> str:
    """Concatena candidatos respeitando o orçamento de contexto."""
    selected: list[str] = []
    used = 0
    for candidate in candidates:
        cleaned = candidate.strip()
        if not cleaned:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        selected.append(cleaned[:remaining])
        used += len(selected[-1]) + 2
    return "\n\n".join(selected)


def _classification_model_name(settings) -> str:
    """Resolve o modelo usado para classificação conforme o provider."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return settings.openai_classification_model
    if provider == "ollama":
        return settings.ollama_classification_model
    return provider
