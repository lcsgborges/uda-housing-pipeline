import logging
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.repository import DocumentRepository
from app.modules.extraction.service import ExtractionService
from app.modules.ingestion.downloader import PDFDownloader
from app.modules.ingestion.hashing import sha256_bytes
from app.modules.ingestion.scraper import RIScraper

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, session: Session):
        self.session = session
        settings = get_settings()
        self.settings = settings
        self.scraper = RIScraper(settings.request_timeout_seconds, settings.user_agent)
        self.downloader = PDFDownloader(settings.request_timeout_seconds, settings.user_agent)
        self.document_repo = DocumentRepository(session)
        self.extraction_service = ExtractionService(session)

    def run(self, company_id: int | None = None) -> dict:
        stmt = select(Company).where(Company.is_active.is_(True))
        if company_id is not None:
            stmt = stmt.where(Company.id == company_id)
        companies = list(self.session.scalars(stmt).all())

        discovered = 0
        processed = 0
        ignored = 0

        for company in companies:
            links = self.scraper.find_pdf_links(company.ri_url)
            for link in links:
                discovered += 1
                outcome = self._ingest_link(company, link["url"], link.get("title"))
                if outcome == "processed":
                    processed += 1
                elif outcome == "ignored":
                    ignored += 1

        return {
            "companies": len(companies),
            "discovered": discovered,
            "processed": processed,
            "ignored_duplicates": ignored,
        }

    def _ingest_link(self, company: Company, url: str, title: str | None) -> str:
        collected_at = datetime.utcnow()
        content = self.downloader.download(url, self.settings.documents_dir)
        file_hash = sha256_bytes(content)

        existing = self.document_repo.get_by_hash(file_hash)
        if existing:
            duplicate = Document(
                company_id=company.id,
                title=title,
                original_url=url,
                local_path=None,
                file_hash=file_hash,
                year=existing.year,
                quarter=existing.quarter,
                document_type=existing.document_type,
                status=DocumentStatus.ignored_duplicate,
                collected_at=collected_at,
                processed_at=None,
                error_message="Documento duplicado por hash.",
            )
            self.document_repo.create(duplicate)
            return "ignored"

        filename = f"{company.ticker.lower()}_{file_hash[:12]}.pdf"
        file_path = Path(self.settings.documents_dir) / filename
        file_path.write_bytes(content)

        year, quarter = infer_period(url=url, title=title or "")
        document_type = infer_document_type(title or url)
        document = Document(
            company_id=company.id,
            title=title,
            original_url=url,
            local_path=str(file_path),
            file_hash=file_hash,
            year=year,
            quarter=quarter,
            document_type=document_type,
            status=DocumentStatus.downloaded,
            collected_at=collected_at,
            processed_at=None,
            error_message=None,
        )
        document = self.document_repo.create(document)

        self.extraction_service.process_document(document, company_name=company.name)
        logger.info("Documento processado: company=%s url=%s", company.ticker, url)
        return "processed"


def infer_period(url: str, title: str) -> tuple[int | None, int | None]:
    text = f"{url} {title}".lower()
    quarter_match = re.search(r"([1-4])t", text)
    year_match = re.search(r"(20\d{2})", text)
    year_short_match = re.search(r"\b(\d{2})\b", text)

    quarter = int(quarter_match.group(1)) if quarter_match else None
    year = int(year_match.group(1)) if year_match else None

    if year is None and year_short_match:
        yy = int(year_short_match.group(1))
        if yy <= 50:
            year = 2000 + yy

    return year, quarter


def infer_document_type(text: str) -> str:
    lowered = text.lower()
    if "prévia" in lowered or "previa" in lowered:
        return "previa_operacional"
    if "resultado" in lowered:
        return "resultado_trimestral"
    return "outro"
