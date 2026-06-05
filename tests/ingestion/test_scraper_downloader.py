import pytest

from app.modules.ingestion import downloader as downloader_module
from app.modules.ingestion import scraper as scraper_module
from app.modules.ingestion.downloader import PDFDownloader
from app.modules.ingestion.scraper import RIScraper


class _Response:
    def __init__(self, *, text: str = "", content: bytes = b""):
        """Inicializa resposta HTTP fake com texto ou bytes."""
        self.text = text
        self.content = content
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        """Registra que a validação de status foi chamada."""
        self.raise_for_status_called = True


class _FakeClient:
    def __init__(self, response: _Response):
        """Inicializa cliente HTTP fake com resposta fixa."""
        self.response = response
        self.requests = []

    def __enter__(self):
        """Entra no contexto do cliente fake."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Sai do contexto sem suprimir exceções."""
        return None

    def get(self, url):
        """Registra URL consultada e retorna resposta fixa."""
        self.requests.append(url)
        return self.response


def test_ri_scraper_encontra_pdfs_e_prioriza_previa(monkeypatch):
    """Valida descoberta de PDFs e priorização de prévia operacional."""
    html = """
    <html>
      <a href="/downloads/previa-3t25.pdf">Previa Operacional 3T25</a>
            <a href="https://api.mziq.com/mzfilemanager/v2/d/abc/arquivo?origin=2">
                Resultado 3T25
            </a>
            <a href="https://api.mziq.com/mzfilemanager/v2/d/abc/arquivo?origin=2">
                Resultado 3T25 duplicado
            </a>
      <a href="/downloads/apresentacao-3t25.pdf">Apresentação institucional</a>
      <a href="/downloads/noticia.html">Notícia</a>
    </html>
    """
    response = _Response(text=html)
    fake_client = _FakeClient(response)
    monkeypatch.setattr(scraper_module.httpx, "Client", lambda **kwargs: fake_client)

    links = RIScraper(timeout=3, user_agent="agent").find_pdf_links("https://ri.mrv.com.br/base/")

    assert response.raise_for_status_called is True
    assert len(links) == 3
    assert links[0]["title"] == "Previa Operacional 3T25"
    assert links[0]["url"] == "https://ri.mrv.com.br/downloads/previa-3t25.pdf"
    assert links[0]["score"] > links[1]["score"]
    assert any(link["url"].startswith("https://api.mziq.com/mzfilemanager/") for link in links)


def test_pdf_downloader_baixa_conteudo(monkeypatch, tmp_path):
    """Garante que downloader retorna bytes e valida status HTTP."""
    response = _Response(content=b"%PDF")
    fake_client = _FakeClient(response)
    monkeypatch.setattr(downloader_module.httpx, "Client", lambda **kwargs: fake_client)

    content = PDFDownloader(timeout=3, user_agent="agent").download(
        "https://ri.mrv.com.br/doc.pdf",
        tmp_path,
    )

    assert content == b"%PDF"
    assert fake_client.requests == ["https://ri.mrv.com.br/doc.pdf"]
    assert response.raise_for_status_called is True


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/a.pdf", "a.pdf"),
        ("https://example.com/download", "download.pdf"),
        ("https://example.com/", "document.pdf"),
    ],
)
def test_pdf_downloader_make_filename(url, expected):
    """Valida geração de nome de arquivo a partir da URL."""
    assert PDFDownloader(timeout=3, user_agent="agent").make_filename(url) == expected
