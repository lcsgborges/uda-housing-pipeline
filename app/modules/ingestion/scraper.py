import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

KEYWORDS = [
    "prévia operacional",
    "previa operacional",
    "resultados",
    "resultado trimestral",
    "divulgação de resultados",
]


class RIScraper:
    def __init__(self, timeout: int, user_agent: str):
        self.timeout = timeout
        self.user_agent = user_agent

    def find_pdf_links(self, base_url: str) -> list[dict]:
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            response = client.get(base_url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        links: list[dict] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            text = (anchor.get_text(" ", strip=True) or "").lower()
            absolute_url = urljoin(base_url, href)
            if not re.search(r"\.pdf($|\?)", absolute_url.lower()):
                continue
            score = self._score_link(text + " " + absolute_url.lower())
            links.append({"url": absolute_url, "title": anchor.get_text(strip=True) or "PDF", "score": score})

        links.sort(key=lambda item: item["score"], reverse=True)
        return links

    def _score_link(self, text: str) -> int:
        return sum(2 for keyword in KEYWORDS if keyword in text)
