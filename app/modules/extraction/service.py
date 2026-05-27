from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.documents.models import Document, DocumentStatus
from app.modules.extraction.chunking import SemanticChunker
from app.modules.extraction.llm_client import build_llm_client
from app.modules.extraction.pdf_parser import PDFParser
from app.modules.lineage.models import DataLineage
from app.modules.metrics.models import Metric


class ExtractionService:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self.parser = PDFParser()
        self.chunker = SemanticChunker()
        self.llm = build_llm_client()

    def process_document(self, document: Document, company_name: str) -> None:
        document.status = DocumentStatus.processing
        self.session.add(document)
        self.session.commit()

        try:
            parsed = self.parser.parse(document.local_path or "")
            chunks = self.chunker.build_chunks(parsed.pages_text)
            relevant_chunks = self.chunker.select_relevant_chunks(chunks)
            context = "\n\n".join(
                [f"[Página {chunk.page}]\n{chunk.text}" for chunk in relevant_chunks]
            )

            extracted = self.llm.extract_metrics(
                company=company_name,
                original_url=document.original_url,
                context=context,
                year=document.year,
                quarter=document.quarter,
            )

            metric_rows: list[Metric] = []
            lineage_rows: list[DataLineage] = []
            for item in extracted.metrics:
                metric = Metric(
                    company_id=document.company_id,
                    document_id=document.id,
                    metric_name=item.metric_name,
                    metric_category=item.metric_category,
                    period_year=item.period_year,
                    period_quarter=item.period_quarter,
                    value=item.value,
                    unit=item.unit,
                    currency=item.currency,
                    source_page=item.source_page,
                    source_excerpt=item.source_excerpt,
                    confidence=item.confidence,
                )
                metric_rows.append(metric)

            self.session.add_all(metric_rows)
            self.session.commit()
            for metric in metric_rows:
                self.session.refresh(metric)
                lineage_rows.append(
                    DataLineage(
                        metric_id=metric.id,
                        document_id=document.id,
                        original_url=document.original_url,
                        file_hash=document.file_hash or "",
                        source_page=metric.source_page,
                        source_excerpt=metric.source_excerpt,
                        extraction_model=self.settings.openai_model
                        if self.settings.llm_provider == "openai"
                        else "fake-model",
                        extraction_prompt_version=self.settings.extraction_prompt_version,
                        extracted_at=datetime.utcnow(),
                    )
                )

            self.session.add_all(lineage_rows)
            document.status = DocumentStatus.processed
            document.processed_at = datetime.utcnow()
            document.error_message = None
            self.session.add(document)
            self.session.commit()
        except Exception as exc:
            document.status = DocumentStatus.failed
            document.error_message = str(exc)
            self.session.add(document)
            self.session.commit()
            raise
