from dataclasses import dataclass

import fitz


@dataclass
class ParsedPDF:
    full_text: str
    pages_count: int
    pages_text: list[str]
    metadata: dict


class PDFParser:
    def parse(self, file_path: str) -> ParsedPDF:
        doc = fitz.open(file_path)
        parsed = self._parse_doc(doc)
        doc.close()
        return parsed

    def parse_bytes(self, content: bytes) -> ParsedPDF:
        doc = fitz.open(stream=content, filetype="pdf")
        parsed = self._parse_doc(doc)
        doc.close()
        return parsed

    def _parse_doc(self, doc: fitz.Document) -> ParsedPDF:
        pages_text: list[str] = []
        for page in doc:
            pages_text.append(_extract_page_text(page))
        full_text = "\n\n".join(pages_text)
        metadata = dict(doc.metadata or {})
        pages_count = doc.page_count
        return ParsedPDF(
            full_text=full_text,
            pages_count=pages_count,
            pages_text=pages_text,
            metadata=metadata,
        )


def _extract_page_text(page: fitz.Page) -> str:
    blocks = page.get_text("blocks", sort=True)
    block_texts = [block[4].strip() for block in blocks if len(block) > 4 and block[4].strip()]
    if block_texts:
        return "\n\n".join(block_texts)
    return page.get_text("text")
