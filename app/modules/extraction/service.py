import json
import logging
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.core.time import utc_now
from app.modules.documents.models import Document, DocumentStatus
from app.modules.extraction.chunking import Chunk, SemanticChunker
from app.modules.extraction.llm_client import build_llm_client, build_openai_batch_client
from app.modules.extraction.pdf_parser import PDFParser
from app.modules.insights.models import DocumentInsight
from app.modules.lineage.models import DataLineage
from app.modules.metrics.catalog import canonical_metric_name, find_metric_definition
from app.modules.metrics.models import Metric
from app.modules.metrics.schemas import ExtractedMetricBatch
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
        metrics, insights = self._extract_complete_document(
            document=document,
            company_name=company_name,
            pages_text=parsed.pages_text,
        )
        if not metrics and not insights:
            failure_message = "Nenhuma métrica ou insight extraído do documento."
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

        for doc in docs:
            doc.status = DocumentStatus.processing
            doc.error_message = None
            self.session.add(doc)
        await self.session.commit()

        processed = 0
        failed = 0
        for doc in docs:
            company_name = doc.company.name if doc.company else "unknown"
            try:
                parsed = self._parse_document(doc)
                metrics, insights = self._extract_complete_document(
                    document=doc,
                    company_name=company_name,
                    pages_text=parsed.pages_text,
                )
                await self._persist_extraction(
                    document=doc,
                    metrics=metrics,
                    insights=insights,
                )
            except Exception as exc:
                _mark_document_failed(doc, str(exc))
                self.session.add(doc)
                failed += 1
                await self.session.commit()
                continue
            processed += 1
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

    async def submit_openai_extraction_batch(self, batch_size: int | None = None) -> dict:
        """Submete documentos úteis para processamento assíncrono na OpenAI Batch API."""
        self._ensure_openai_provider()
        size = batch_size or self.settings.extraction_batch_size
        docs = await self._select_classified_documents(size)
        if not docs:
            return {"selected": 0, "requests": 0, "batch_id": None, "input_file_id": None}

        batch_client = build_openai_batch_client()
        requests: list[dict] = []
        for doc in docs:
            company_name = doc.company.name if doc.company else "unknown"
            parsed = self._parse_document(doc)
            contexts = self._build_contexts(parsed.pages_text)
            for part, context in enumerate(contexts, start=1):
                payload = self._build_extraction_payload(
                    document=doc,
                    company_name=company_name,
                    context=context,
                    part=part,
                )
                custom_id = _build_openai_batch_custom_id(
                    document_id=doc.id,
                    part=part,
                    total_parts=len(contexts),
                )
                requests.append(
                    batch_client.build_extraction_request(
                        custom_id=custom_id,
                        payload=payload,
                    )
                )

        uploaded, batch = batch_client.submit_requests(requests)
        for doc in docs:
            doc.status = DocumentStatus.processing
            doc.error_message = f"OpenAI batch pendente: {batch.id}"
            self.session.add(doc)
        await self.session.commit()

        return {
            "selected": len(docs),
            "requests": len(requests),
            "batch_id": batch.id,
            "input_file_id": uploaded.id,
            "status": batch.status,
        }

    def get_openai_extraction_batch_status(self, batch_id: str) -> dict:
        """Consulta o status de um batch assíncrono da OpenAI."""
        self._ensure_openai_provider()
        batch = build_openai_batch_client().retrieve_batch(batch_id)
        return _openai_object_to_dict(batch)

    async def import_openai_extraction_batch(self, batch_id: str) -> dict:
        """Baixa o resultado de um batch OpenAI concluído e persiste extrações."""
        self._ensure_openai_provider()
        batch_client = build_openai_batch_client()
        batch = batch_client.retrieve_batch(batch_id)
        if batch.status != "completed":
            return {
                "batch_id": batch.id,
                "status": batch.status,
                "imported": 0,
                "failed": 0,
                "message": "Batch ainda não está completed.",
            }
        if not batch.output_file_id:
            raise ValueError("Batch concluído sem output_file_id.")

        output_text = batch_client.download_file_text(batch.output_file_id)
        grouped = _parse_openai_batch_output(output_text)

        imported = 0
        failed = 0
        for document_id, group in grouped.items():
            document = await self.session.get(Document, document_id)
            if document is None:
                failed += 1
                continue
            try:
                metrics, insights = _collect_openai_batch_group(group)
                await self._persist_extraction(
                    document=document,
                    metrics=metrics,
                    insights=insights,
                )
            except Exception as exc:
                _mark_document_failed(document, str(exc))
                self.session.add(document)
                await self.session.commit()
                failed += 1
                continue
            imported += 1

        return {
            "batch_id": batch.id,
            "status": batch.status,
            "imported": imported,
            "failed": failed,
            "output_file_id": batch.output_file_id,
            "error_file_id": batch.error_file_id,
        }

    async def _select_classified_documents(self, size: int) -> list[Document]:
        """Seleciona documentos úteis pendentes para extração."""
        stmt = (
            select(Document)
            .options(joinedload(Document.company))
            .where(Document.status == DocumentStatus.classified_useful)
            .order_by(Document.collected_at.asc())
            .limit(size)
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    def _ensure_openai_provider(self) -> None:
        """Garante que o fluxo Batch API seja usado apenas com provider OpenAI."""
        if self.settings.llm_provider.lower() not in {"openai", "chatgpt"}:
            raise ValueError("OpenAI Batch API exige LLM_PROVIDER=openai.")

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

    def _extract_complete_document(
        self,
        *,
        document: Document,
        company_name: str,
        pages_text: list[str],
    ) -> tuple[list, list]:
        """Varre todas as partes do documento em batches e consolida os resultados."""
        contexts = self._build_contexts(pages_text)
        payloads = [
            self._build_extraction_payload(
                document=document,
                company_name=company_name,
                context=context,
                part=index,
            )
            for index, context in enumerate(contexts, start=1)
        ]
        collected_metrics: list = []
        collected_insights: list = []

        for payload_batch in _split_payloads_for_llm_batch(
            payloads,
            max_chars=self.settings.extraction_llm_batch_max_chars,
        ):
            metrics, insights = self._extract_payload_batch(payload_batch)
            collected_metrics.extend(metrics)
            collected_insights.extend(insights)

        return _deduplicate_metrics(collected_metrics), _deduplicate_insights(collected_insights)

    def _extract_payload_batch(self, payloads: list[dict]) -> tuple[list, list]:
        """Extrai dados de um batch de partes, com fallback individual em falhas."""
        try:
            batch = self.llm.extract_metrics_batch(payloads)
        except Exception as exc:
            return self._extract_payloads_individually(payloads, error=str(exc))

        collected_metrics: list = []
        collected_insights: list = []
        for payload in payloads:
            batch_item = _find_batch_item(
                batch.documents,
                payload,
                allow_base_ref=len(payloads) == 1,
            )
            metrics = batch_item.metrics if batch_item else None
            insights = batch_item.insights if batch_item else None
            if metrics or insights:
                collected_metrics.extend(list(metrics or []))
                collected_insights.extend(list(insights or []))
                continue
            if batch_item is None:
                metrics, insights = self._extract_payload(payload)
                collected_metrics.extend(metrics)
                collected_insights.extend(insights)

        return collected_metrics, collected_insights

    def _extract_payloads_individually(
        self,
        payloads: list[dict],
        *,
        error: str,
    ) -> tuple[list, list]:
        """Reprocessa partes individualmente quando a chamada batch falha."""
        logger.warning("Batch da LLM falhou; usando fallback individual: %s", error)
        collected_metrics: list = []
        collected_insights: list = []
        for payload in payloads:
            metrics, insights = self._extract_payload(payload)
            collected_metrics.extend(metrics)
            collected_insights.extend(insights)
        return collected_metrics, collected_insights

    def _build_extraction_payload(
        self,
        *,
        document: Document,
        company_name: str,
        context: str,
        part: int,
    ) -> dict:
        """Monta o payload enviado à LLM para uma parte do documento."""
        return {
            "document_ref": f"{document.id}:part:{part}",
            "company": company_name,
            "title": document.title,
            "document_type": document.document_type,
            "original_url": document.original_url,
            "year": document.year,
            "quarter": document.quarter,
            "context": context,
        }

    def _extract_payload(self, payload: dict) -> tuple[list, list]:
        """Extrai dados de um payload pequeno, com retry individual quando necessário."""
        try:
            batch = self.llm.extract_metrics_batch([payload])
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        batch_item = _find_batch_item(batch.documents, payload, allow_base_ref=True)
        metrics = batch_item.metrics if batch_item else None
        insights = batch_item.insights if batch_item else None
        if metrics or insights:
            return list(metrics or []), list(insights or [])

        retry_response, retry_error = self._extract_single_document(payload)
        if retry_error:
            logger.warning(
                "Retry individual falhou para payload %s: %s",
                payload["document_ref"],
                retry_error,
            )
            if batch_item is None:
                raise RuntimeError(
                    f"Documento não retornado no batch da LLM. Retry individual falhou: "
                    f"{retry_error}"
                )
            raise RuntimeError(
                f"Nenhuma métrica ou insight extraído do payload. Retry individual falhou: "
                f"{retry_error}"
            )
        return list(retry_response.metrics), list(retry_response.insights)

    def _parse_document(self, document: Document):
        """Lê e parseia um documento a partir de path local ou storage URI."""
        if not document.local_path:
            raise ValueError("Documento sem local_path para leitura.")
        if _is_storage_uri(document.local_path):
            content = self.storage.read(document.local_path)
            return self.parser.parse_bytes(content)
        return self.parser.parse(document.local_path)

    def _build_context(self, pages_text: list[str]) -> str:
        """Monta o primeiro contexto de extração para compatibilidade interna."""
        return self._build_contexts(pages_text)[0]

    def _build_contexts(self, pages_text: list[str]) -> list[str]:
        """Monta contextos que cobrem o documento inteiro em partes sequenciais."""
        full_text = "\n\n".join(
            [f"[Página {index}]\n{text}" for index, text in enumerate(pages_text, start=1)]
        )
        if len(full_text) <= self.settings.extraction_full_scan_max_chars:
            logger.info("Extração em modo full_scan (chars=%s)", len(full_text))
            return [f"[MODO full_scan]\n{full_text}"]

        chunks = _split_pages_into_sequential_contexts(
            pages_text,
            max_chars=self.settings.extraction_context_max_chars,
        )
        logger.info(
            "Extração em modo sequential_scan (parts=%s, max_chars=%s)",
            len(chunks),
            self.settings.extraction_context_max_chars,
        )
        return [
            f"[MODO sequential_scan | parte {index}/{len(chunks)}]\n{chunk}"
            for index, chunk in enumerate(chunks, start=1)
        ]


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


def _split_pages_into_sequential_contexts(pages_text: list[str], *, max_chars: int) -> list[str]:
    """Divide o texto completo em partes sequenciais respeitando páginas e limite."""
    blocks = _build_page_blocks(pages_text, max_chars=max_chars)
    contexts: list[str] = []
    current_blocks: list[str] = []
    current_size = 0

    for block in blocks:
        separator_size = 2 if current_blocks else 0
        next_size = current_size + separator_size + len(block)
        if current_blocks and next_size > max_chars:
            contexts.append("\n\n".join(current_blocks))
            current_blocks = [block]
            current_size = len(block)
            continue
        current_blocks.append(block)
        current_size = next_size

    if current_blocks:
        contexts.append("\n\n".join(current_blocks))
    return contexts or ["[Sem texto extraível]"]


def _build_page_blocks(pages_text: list[str], *, max_chars: int) -> list[str]:
    """Cria blocos por página e quebra páginas que excedem o tamanho permitido."""
    blocks: list[str] = []
    for page, text in enumerate(pages_text, start=1):
        cleaned = text.strip()
        if not cleaned:
            continue
        header = f"[Página {page}]"
        block = f"{header}\n{cleaned}"
        if len(block) <= max_chars:
            blocks.append(block)
            continue

        available = max(500, max_chars - len(header) - 32)
        parts = _split_text(cleaned, max_chars=available)
        for part_index, part in enumerate(parts, start=1):
            blocks.append(f"[Página {page} | trecho {part_index}/{len(parts)}]\n{part}")
    return blocks


def _split_text(text: str, *, max_chars: int) -> list[str]:
    """Quebra um texto longo em fatias, preferindo limites de linha."""
    parts: list[str] = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= max_chars:
            parts.append(remaining)
            break
        boundary = remaining.rfind("\n", 0, max_chars)
        if boundary < max_chars // 2:
            boundary = remaining.rfind(" ", 0, max_chars)
        if boundary < max_chars // 2:
            boundary = max_chars
        parts.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    return [part for part in parts if part]


def _split_payloads_for_llm_batch(payloads: list[dict], *, max_chars: int) -> list[list[dict]]:
    """Agrupa payloads em lotes síncronos respeitando um orçamento aproximado."""
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_size = 0
    for payload in payloads:
        payload_size = _payload_size(payload)
        if current and current_size + payload_size > max_chars:
            batches.append(current)
            current = [payload]
            current_size = payload_size
            continue
        current.append(payload)
        current_size += payload_size
    if current:
        batches.append(current)
    return batches


def _payload_size(payload: dict) -> int:
    """Calcula tamanho aproximado do payload que entra no prompt."""
    return len(json.dumps(payload, ensure_ascii=False))


def _find_batch_item(documents: list, payload: dict, *, allow_base_ref: bool):
    """Localiza a resposta correspondente a um payload no contrato batch."""
    accepted_refs = {payload["document_ref"]}
    if allow_base_ref:
        accepted_refs.add(payload["document_ref"].split(":part:", maxsplit=1)[0])
    return next((item for item in documents if item.document_ref in accepted_refs), None)


def _build_openai_batch_custom_id(*, document_id: int, part: int, total_parts: int) -> str:
    """Codifica documento e parte em um custom_id estável para a Batch API."""
    return f"document-{document_id}-part-{part}-of-{total_parts}"


def _parse_openai_batch_custom_id(custom_id: str) -> dict:
    """Decodifica custom_id gerado para a Batch API."""
    pattern = r"document-(?P<document_id>\d+)-part-(?P<part>\d+)-of-(?P<total>\d+)"
    match = re.fullmatch(pattern, custom_id)
    if not match:
        raise ValueError(f"custom_id inválido: {custom_id}")
    return {
        "document_id": int(match.group("document_id")),
        "part": int(match.group("part")),
        "total": int(match.group("total")),
    }


def _parse_openai_batch_output(output_text: str) -> dict[int, dict]:
    """Agrupa linhas JSONL de saída da OpenAI por documento."""
    grouped = defaultdict(lambda: {"total": None, "parts": {}, "errors": []})
    for line in output_text.splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        custom_id = raw["custom_id"]
        meta = _parse_openai_batch_custom_id(custom_id)
        group = grouped[meta["document_id"]]
        group["total"] = meta["total"]
        if raw.get("error"):
            group["errors"].append({"part": meta["part"], "error": raw["error"]})
            continue

        response = raw.get("response") or {}
        status_code = response.get("status_code")
        body = response.get("body") or {}
        if status_code != 200:
            group["errors"].append({"part": meta["part"], "error": body or response})
            continue

        extracted_text = _extract_response_output_text(body)
        group["parts"][meta["part"]] = ExtractedMetricBatch.model_validate_json(extracted_text)
    return dict(grouped)


def _extract_response_output_text(body: dict) -> str:
    """Extrai o texto JSON estruturado de uma resposta `/v1/responses`."""
    if isinstance(body.get("output_text"), str):
        return body["output_text"]
    for output in body.get("output", []):
        for content in output.get("content", []):
            if isinstance(content.get("text"), str):
                return content["text"]
    raise ValueError("Resposta da OpenAI sem output_text.")


def _collect_openai_batch_group(group: dict) -> tuple[list, list]:
    """Consolida todas as partes de um documento retornadas pela Batch API."""
    if group["errors"]:
        raise ValueError(f"Batch retornou erros em partes: {group['errors']}")
    total = group["total"]
    parts = group["parts"]
    if not total or len(parts) != total:
        raise ValueError(f"Batch incompleto: {len(parts)}/{total or 0} partes retornadas.")

    metrics: list = []
    insights: list = []
    for part in range(1, total + 1):
        payload = parts[part]
        metrics.extend(payload.metrics)
        insights.extend(payload.insights)
    return _deduplicate_metrics(metrics), _deduplicate_insights(insights)


def _openai_object_to_dict(value) -> dict:
    """Converte objetos do SDK OpenAI para dict JSON-friendly."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _deduplicate_metrics(metrics: list) -> list:
    """Remove métricas repetidas mantendo a primeira ocorrência."""
    seen: set[tuple] = set()
    deduplicated = []
    for metric in metrics:
        key = (
            canonical_metric_name(metric.metric_name),
            metric.period_year,
            metric.period_quarter,
            metric.period_label,
            metric.dimension,
            metric.value,
            metric.unit,
            metric.currency,
            metric.source_page,
            _normalize_key_text(metric.source_excerpt),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(metric)
    return deduplicated


def _deduplicate_insights(insights: list) -> list:
    """Remove insights repetidos mantendo a primeira ocorrência."""
    seen: set[tuple] = set()
    deduplicated = []
    for insight in insights:
        key = (
            insight.insight_type,
            insight.topic,
            _normalize_key_text(insight.summary),
            _normalize_key_text(insight.value_text),
            insight.period_year,
            insight.period_quarter,
            insight.source_page,
            _normalize_key_text(insight.source_excerpt),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(insight)
    return deduplicated


def _normalize_key_text(value: str | None) -> str | None:
    """Normaliza texto usado em chaves de deduplicação."""
    if value is None:
        return None
    return " ".join(value.casefold().split())


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
