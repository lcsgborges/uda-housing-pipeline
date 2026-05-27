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
        pages_text: list[str] = []
        for page in doc:
            pages_text.append(page.get_text("text"))
        full_text = "\n\n".join(pages_text)
        metadata = dict(doc.metadata or {})
        pages_count = doc.page_count
        doc.close()
        return ParsedPDF(
            full_text=full_text,
            pages_count=pages_count,
            pages_text=pages_text,
            metadata=metadata,
        )
