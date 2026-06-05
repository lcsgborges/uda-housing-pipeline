import pytest

from app.modules.ingestion import downloader as downloader_module
from app.modules.ingestion import scraper as scraper_module
from app.modules.ingestion.downloader import PDFDownloader
from app.modules.ingestion.scraper import RIScraper


class _Response:
    def __init__(self, *, text: str = "", content: bytes = b"", json_data=None):
        """Inicializa resposta HTTP fake com texto ou bytes."""
        self.text = text
        self.content = content
        self.json_data = json_data
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        """Registra que a validação de status foi chamada."""
        self.raise_for_status_called = True

    def json(self):
        """Retorna payload JSON configurado para a resposta fake."""
        return self.json_data


class _FakeClient:
    def __init__(
        self,
        response: _Response | None = None,
        responses: dict[str, _Response] | None = None,
    ):
        """Inicializa cliente HTTP fake com resposta fixa ou mapeada por URL."""
        self.response = response
        self.responses = responses or {}
        self.requests = []
        self.posts = []

    def __enter__(self):
        """Entra no contexto do cliente fake."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Sai do contexto sem suprimir exceções."""
        return None

    def get(self, url):
        """Registra URL consultada e retorna resposta fixa."""
        self.requests.append(url)
        return self.responses.get(url) or self.response

    def post(self, url, json=None):
        """Registra POST consultado e retorna resposta mapeada."""
        self.posts.append((url, json))
        return self.responses[url]


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


def test_ri_scraper_busca_resultados_mziq_de_todos_os_anos(monkeypatch):
    """Valida busca MZiQ por todos os anos e só nas três primeiras categorias."""
    page_url = "https://ri.mrv.com.br/informacoes-financeiras/central-de-resultados/"
    api_url = (
        "https://apicatalog.mziq.com/filemanager/company/company-id/filter/categories/meta"
    )
    html = """
    <html>
      <script>
        var fmId = 'company-id';
        var fmBase = 'https://apicatalog.mziq.com/filemanager';
        var language = 'pt-BR';
        var categories = [];
        categories.push({
          title: 'Earnings Release',
          internal_name: 'central_de_resultados_release'
        })
        categories.push({
          title: 'Prévia Operacional',
          internal_name: 'central_de_resultados_previa'
        })
        categories.push({ title: 'ITR/DFP', internal_name: 'central_de_resultados_itr' })
        categories.push({
          title: 'Planilha Interativa',
          internal_name: 'central_de_resultados_planilha_interativa'
        })
        categories.push({ title: 'Audio', internal_name: 'central_de_resultados_audio' })
        categories.push({
          title: 'Transcrição',
          internal_name: 'central_de_resultados_transcricao'
        })
        var configPage = { language: 'pt_BR' };
      </script>
      <header>
        <a href="https://api.mziq.com/mzfilemanager/v2/d/company-id/menu?origin=2">ESG</a>
      </header>
    </html>
    """
    document_metas = [
        _mziq_document("central_de_resultados_release", "Earnings Release 1T26", 2026, 1, "er26"),
        _mziq_document("central_de_resultados_previa", "Prévia Operacional 1T26", 2026, 1, "pre26"),
        _mziq_document("central_de_resultados_itr", "ITR/DFP 1T26", 2026, 1, "itr26"),
        _mziq_document("central_de_resultados_release", "Earnings Release 4T25", 2025, 4, "er25"),
        _mziq_document("central_de_resultados_previa", "Prévia Operacional 4T25", 2025, 4, "pre25"),
        _mziq_document("central_de_resultados_itr", "ITR/DFP 4T25", 2025, 4, "itr25"),
        _mziq_document(
            "central_de_resultados_planilha_interativa",
            "Planilha Interativa 4T25",
            2025,
            4,
            "xls25",
        ),
    ]
    responses = {
        page_url: _Response(text=html),
        api_url: _Response(json_data={"success": True, "data": {"document_metas": document_metas}}),
    }
    fake_client = _FakeClient(responses=responses)
    monkeypatch.setattr(scraper_module.httpx, "Client", lambda **kwargs: fake_client)

    links = RIScraper(timeout=3, user_agent="agent").find_pdf_links(page_url)

    assert fake_client.posts == [
        (
            api_url,
            {
                "categoryInternalNames": [
                    "central_de_resultados_release",
                    "central_de_resultados_previa",
                    "central_de_resultados_itr",
                ],
                "language": "pt_BR",
                "published": True,
            },
        )
    ]
    assert len(links) == 6
    assert {link["title"] for link in links} == {
        "Earnings Release 1T26",
        "Prévia Operacional 1T26",
        "ITR/DFP 1T26",
        "Earnings Release 4T25",
        "Prévia Operacional 4T25",
        "ITR/DFP 4T25",
    }
    assert all("menu" not in link["url"] for link in links)
    assert all("xls25" not in link["url"] for link in links)


def _mziq_document(internal_name: str, title: str, year: int, quarter: int, slug: str) -> dict:
    """Cria documento MZiQ fake no mesmo formato usado pela API pública."""
    return {
        "category_internal_name": internal_name,
        "file_title": title,
        "file_year": year,
        "file_quarter": quarter,
        "permalink": (
            "https://api.mziq.com/mzfilemanager/v2/d/company-id/"
            f"{slug}?origin=2"
        ),
    }


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
