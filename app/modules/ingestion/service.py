import logging
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.companies.models import Company
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.repository import DocumentRepository
from app.modules.extraction.service import ExtractionService
from app.modules.ingestion.downloader import PDFDownloader
from app.modules.ingestion.hashing import sha256_bytes
from app.modules.ingestion.scraper import RIScraper
from app.modules.storage.service import build_object_storage

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        settings = get_settings()
        self.settings = settings
        self.scraper = RIScraper(settings.request_timeout_seconds, settings.user_agent)
        self.downloader = PDFDownloader(settings.request_timeout_seconds, settings.user_agent)
        self.document_repo = DocumentRepository(session)
        self.extraction_service = ExtractionService(session)
        self.storage = build_object_storage()

    async def run(
        self,
        company_id: int | None = None,
        extract_after_ingestion: bool = True,
    ) -> dict:
        stmt = select(Company).where(Company.is_active.is_(True))
        if company_id is not None:
            stmt = stmt.where(Company.id == company_id)
        result = await self.session.scalars(stmt)
        companies = list(result.all())

        discovered = 0
        processed = 0
        ignored = 0

        for company in companies:
            links = self.scraper.find_pdf_links(company.ri_url)
            for link in links:
                discovered += 1
                outcome = await self._ingest_link(
                    company,
                    link["url"],
                    link.get("title"),
                    extract_after_ingestion=extract_after_ingestion,
                )
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

    async def _ingest_link(
        self,
        company: Company,
        url: str,
        title: str | None,
        extract_after_ingestion: bool = True,
    ) -> str:
        collected_at = datetime.utcnow()
        content = self.downloader.download(url, self.settings.documents_dir)
        file_hash = sha256_bytes(content)

        existing = await self.document_repo.get_by_hash(file_hash)
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
            await self.document_repo.create(duplicate)
            return "ignored"

        filename = f"{company.ticker.lower()}_{file_hash[:12]}.pdf"
        storage_key = f"{company.ticker.lower()}/{filename}"
        stored = self.storage.store(key=storage_key, content=content)

        year, quarter = infer_period(url=url, title=title or "")
        document_type = infer_document_type(title or url)
        document = Document(
            company_id=company.id,
            title=title,
            original_url=url,
            local_path=stored.uri,
            file_hash=file_hash,
            year=year,
            quarter=quarter,
            document_type=document_type,
            status=DocumentStatus.downloaded,
            collected_at=collected_at,
            processed_at=None,
            error_message=None,
        )
        document = await self.document_repo.create(document)

        if extract_after_ingestion:
            await self.extraction_service.process_document(document, company_name=company.name)
        logger.info("Documento ingerido: company=%s url=%s", company.ticker, url)
        return "processed"


def infer_period(url: str, title: str) -> tuple[int | None, int | None]:
    text = f"{url} {title}".lower()
    quarter_year_match = re.search(r"([1-4])t[\s_-]?(20\d{2}|\d{2})", text)
    quarter_match = re.search(r"([1-4])t", text)
    year_match = re.search(r"(20\d{2})", text)
    year_short_match = re.search(r"\b(\d{2})\b", text)

    quarter = int(quarter_match.group(1)) if quarter_match else None
    year = int(year_match.group(1)) if year_match else None

    if quarter_year_match:
        quarter = int(quarter_year_match.group(1))
        compact_year = quarter_year_match.group(2)
        year = int(compact_year) if len(compact_year) == 4 else 2000 + int(compact_year)

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
