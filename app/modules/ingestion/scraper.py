import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.text import normalize_for_search

KEYWORDS = [
    "prévia operacional",
    "resultados",
    "resultado trimestral",
    "divulgação de resultados",
    "earnings release",
    "release de resultados",
    "relatório de sustentabilidade",
    "sustentabilidade",
    "esg",
]


class RIScraper:
    def __init__(self, timeout: int, user_agent: str):
        """Inicializa o scraper HTTP com timeout e User-Agent configurados."""
        self.timeout = timeout
        self.user_agent = user_agent

    def find_pdf_links(self, base_url: str) -> list[dict]:
        """Descobre links PDF em uma página de RI e ordena por relevância."""
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            response = client.get(base_url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        links: list[dict] = []
        seen_urls: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            text = anchor.get_text(" ", strip=True) or ""
            absolute_url = urljoin(base_url, href)
            if not self._is_document_link(absolute_url):
                continue
            if absolute_url in seen_urls:
                continue
            seen_urls.add(absolute_url)
            score = self._score_link(f"{text} {absolute_url}")
            links.append(
                {
                    "url": absolute_url,
                    "title": anchor.get_text(strip=True) or "PDF",
                    "score": score,
                }
            )

        links.sort(key=lambda item: item["score"], reverse=True)
        return links

    def _is_document_link(self, url: str) -> bool:
        """Reconhece PDFs diretos e links de gerenciadores de arquivos de RI."""
        lowered = url.lower()
        return bool(
            re.search(r"\.pdf($|\?)", lowered)
            or ("api.mziq.com" in lowered and "mzfilemanager" in lowered)
        )

    def _score_link(self, text: str) -> int:
        """Pontua um link conforme termos relevantes aparecem no texto ou URL."""
        normalized_text = normalize_for_search(text)
        return sum(2 for keyword in KEYWORDS if normalize_for_search(keyword) in normalized_text)
