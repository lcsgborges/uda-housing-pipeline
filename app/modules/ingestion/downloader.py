from pathlib import Path
from urllib.parse import urlparse

import httpx


class PDFDownloader:
    def __init__(self, timeout: int, user_agent: str):
        """Inicializa o downloader HTTP com timeout e User-Agent configurados."""
        self.timeout = timeout
        self.user_agent = user_agent

    def download(self, url: str, destination_dir: Path) -> bytes:
        """Baixa um PDF remoto e retorna seu conteúdo em bytes."""
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
        return response.content

    def make_filename(self, url: str) -> str:
        """Deriva um nome de arquivo PDF a partir da URL original."""
        parsed = urlparse(url)
        name = Path(parsed.path).name or "document.pdf"
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"
        return name
