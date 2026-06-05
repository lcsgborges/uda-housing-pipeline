import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.text import normalize_for_search
from app.core.time import utc_now
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
        """Inicializa dependências de scraping, download, storage e extração."""
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
        """Executa ingestão das empresas ativas e resume documentos processados."""
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

    async def run_scheduled_cycle(self, company_id: int | None = None) -> dict:
        """Executa ciclo diário: ingere novidades e processa pendências em lotes."""
        ingestion = await self.run(company_id=company_id, extract_after_ingestion=False)
        extraction = await self.extraction_service.process_all_pending_documents(
            batch_size=self.settings.extraction_batch_size,
        )
        return {"ingestion": ingestion, "extraction": extraction}

    async def _ingest_link(
        self,
        company: Company,
        url: str,
        title: str | None,
        extract_after_ingestion: bool = True,
    ) -> str:
        """Ingere um link PDF, deduplica por hash e dispara extração opcional."""
        collected_at = utc_now()
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
    """Infere ano e trimestre a partir de padrões comuns em URL e título."""
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
    """Classifica o tipo do documento a partir do texto normalizado."""
    normalized = normalize_for_search(text)
    if "sustentabilidade" in normalized or "esg" in normalized:
        return "relatorio_sustentabilidade"
    if "previa" in normalized:
        return "previa_operacional"
    if (
        "resultado" in normalized
        or "earnings release" in normalized
        or "release de resultados" in normalized
        or "divulgacao de resultados" in normalized
    ):
        return "resultado_trimestral"
    return "outro"
