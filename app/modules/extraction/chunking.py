import re
from dataclasses import dataclass

KEYWORDS = {
    "lançamentos",
    "vendas líquidas",
    "vendas brutas",
    "distratos",
    "vgv",
    "unidades vendidas",
    "estoque",
    "landbank",
    "receita",
    "lucro",
    "margem",
    "trimestre",
    "1t",
    "2t",
    "3t",
    "4t",
}


@dataclass
class Chunk:
    page: int
    text: str
    score: int


class SemanticChunker:
    def __init__(self, max_chars: int = 2200):
        self.max_chars = max_chars

    def build_chunks(self, pages_text: list[str]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for idx, page_text in enumerate(pages_text, start=1):
            blocks = self._split_page(page_text)
            for block in blocks:
                score = self._score_chunk(block)
                chunks.append(Chunk(page=idx, text=block, score=score))
        return chunks

    def select_relevant_chunks(self, chunks: list[Chunk], top_k: int = 8) -> list[Chunk]:
        ranked = sorted(chunks, key=lambda c: c.score, reverse=True)
        positives = [chunk for chunk in ranked if chunk.score > 0]
        return positives[:top_k] if positives else ranked[:top_k]

    def _split_page(self, text: str) -> list[str]:
        paragraphs = [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()]
        if not paragraphs:
            return [text[: self.max_chars]] if text else []

        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 2 <= self.max_chars:
                current = f"{current}\n\n{paragraph}".strip()
            else:
                if current:
                    chunks.append(current)
                current = paragraph[: self.max_chars]
        if current:
            chunks.append(current)
        return chunks

    def _score_chunk(self, text: str) -> int:
        lowered = text.lower()
        return sum(1 for keyword in KEYWORDS if keyword in lowered)
