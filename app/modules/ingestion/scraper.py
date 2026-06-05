import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.core.text import normalize_for_search

KEYWORDS = [
    "prévia operacional",
    "itr/dfp",
    "itr",
    "dfp",
    "resultados",
    "resultado trimestral",
    "divulgação de resultados",
    "earnings release",
    "release de resultados",
    "relatório de sustentabilidade",
    "sustentabilidade",
    "esg",
]
MZIQ_RESULT_CATEGORY_LIMIT = 3
MZIQ_RESULT_CATEGORY_HINTS = ("release", "resultado", "resultados", "previa", "itr", "dfp")
MZIQ_EXCLUDED_CATEGORY_HINTS = ("planilha", "excel", "audio", "transcricao")


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

            self._collect_static_document_links(soup, base_url, links, seen_urls)
            self._collect_mziq_filemanager_links(client, response.text, links, seen_urls)

        links.sort(key=lambda item: item["score"], reverse=True)
        return links

    def _collect_static_document_links(
        self,
        soup: BeautifulSoup,
        base_url: str,
        links: list[dict],
        seen_urls: set[str],
    ) -> None:
        """Coleta PDFs expostos diretamente no HTML, ignorando menus e rodapés."""
        for anchor in soup.find_all("a", href=True):
            if not isinstance(anchor, Tag) or self._is_navigation_link(anchor):
                continue
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

    def _is_document_link(self, url: str) -> bool:
        """Reconhece PDFs diretos e links de gerenciadores de arquivos de RI."""
        lowered = url.lower()
        return bool(
            re.search(r"\.pdf($|\?)", lowered)
            or ("api.mziq.com" in lowered and "mzfilemanager" in lowered)
        )

    def _is_navigation_link(self, anchor: Tag) -> bool:
        """Detecta links em regiões de navegação que não são documentos da página."""
        navigation_tags = {"header", "footer", "nav"}
        navigation_hints = ("menu", "header", "footer", "nav", "topper")

        for parent in anchor.parents:
            if not isinstance(parent, Tag):
                continue
            if parent.name in navigation_tags:
                return True

            classes = parent.get("class") or []
            if isinstance(classes, str):
                classes = [classes]
            attributes = " ".join([str(parent.get("id", "")), *[str(item) for item in classes]])
            normalized_attributes = normalize_for_search(attributes)
            if any(hint in normalized_attributes for hint in navigation_hints):
                return True
        return False

    def _collect_mziq_filemanager_links(
        self,
        client: httpx.Client,
        html: str,
        links: list[dict],
        seen_urls: set[str],
    ) -> None:
        """Busca documentos em páginas que montam tabelas pelo File Manager da MZiQ."""
        settings = self._extract_mziq_settings(html)
        if not settings:
            return

        categories = self._extract_mziq_categories(html)
        selected_categories = self._select_mziq_result_categories(categories)
        if not selected_categories:
            return

        fm_base = settings["fm_base"].rstrip("/")
        url = f"{fm_base}/company/{settings['fm_id']}/filter/categories/meta"
        category_names = [category["internal_name"] for category in selected_categories]
        payload = {
            "categoryInternalNames": category_names,
            "language": settings["language"],
            "published": True,
        }

        try:
            response = client.post(url, json=payload)
            response.raise_for_status()
            response_payload = response.json()
        except (httpx.HTTPError, ValueError):
            return

        if isinstance(response_payload, dict) and response_payload.get("success") is False:
            return

        category_titles = {
            category["internal_name"]: category["title"] for category in selected_categories
        }
        selected_names = set(category_names)
        for document in self._iter_mziq_documents(response_payload):
            internal_name = str(
                document.get("category_internal_name") or document.get("internal_name") or ""
            )
            if internal_name not in selected_names:
                continue

            document_url = self._extract_mziq_document_url(document)
            if not document_url or not self._is_document_link(document_url):
                continue
            if document_url in seen_urls:
                continue

            category_title = category_titles.get(internal_name, "")
            title = self._build_mziq_document_title(document, category_title)
            seen_urls.add(document_url)
            links.append(
                {
                    "url": document_url,
                    "title": title,
                    "score": 10,
                }
            )

    def _extract_mziq_settings(self, html: str) -> dict[str, str] | None:
        """Extrai identificador, base da API e idioma da configuração JavaScript MZiQ."""
        fm_id = self._extract_js_assignment(html, "fmId")
        fm_base = self._extract_js_assignment(html, "fmBase")
        if not fm_id or not fm_base:
            return None

        language = (
            self._extract_object_property(html, "language")
            or self._extract_js_assignment(html, "language")
            or "pt_BR"
        )
        return {
            "fm_id": fm_id,
            "fm_base": fm_base,
            "language": language.replace("-", "_"),
        }

    def _extract_mziq_categories(self, html: str) -> list[dict[str, str]]:
        """Lê as categorias declaradas por `categories.push` na página MZiQ."""
        categories: list[dict[str, str]] = []
        pattern = re.compile(r"categories\.push\s*\(\s*\{(?P<body>.*?)\}\s*\)", re.DOTALL)
        for match in pattern.finditer(html):
            body = match.group("body")
            title = self._extract_object_property(body, "title")
            internal_name = self._extract_object_property(body, "internal_name")
            if title and internal_name:
                categories.append({"title": title, "internal_name": internal_name})
        return categories

    def _select_mziq_result_categories(
        self,
        categories: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Seleciona as categorias PDF de resultado, respeitando a ordem da tabela."""
        selected: list[dict[str, str]] = []
        for category in categories:
            category_text = normalize_for_search(
                f"{category.get('title', '')} {category.get('internal_name', '')}"
            )
            if any(hint in category_text for hint in MZIQ_EXCLUDED_CATEGORY_HINTS):
                continue
            if any(hint in category_text for hint in MZIQ_RESULT_CATEGORY_HINTS):
                selected.append(category)
            if len(selected) == MZIQ_RESULT_CATEGORY_LIMIT:
                return selected

        result_center_categories = [
            category
            for category in categories
            if "central_de_resultados" in normalize_for_search(category.get("internal_name", ""))
        ]
        return result_center_categories[:MZIQ_RESULT_CATEGORY_LIMIT]

    def _extract_mziq_document_url(self, document: dict) -> str:
        """Obtém a URL de download de um documento retornado pela MZiQ."""
        for key in ("link_url", "permalink", "file_url"):
            value = document.get(key)
            if value:
                return str(value)
        return ""

    def _build_mziq_document_title(self, document: dict, category_title: str) -> str:
        """Monta um título informativo com tipo documental e período quando disponível."""
        title = str(
            document.get("file_title")
            or document.get("file_name_original")
            or category_title
            or "PDF"
        ).strip()
        year = document.get("file_year")
        quarter = document.get("file_quarter")

        period = ""
        if isinstance(year, int) and isinstance(quarter, int) and 1 <= quarter <= 4:
            period = f"{quarter}T{str(year)[-2:]}"

        normalized_title = normalize_for_search(title)
        if category_title and normalize_for_search(category_title) not in normalized_title:
            title = f"{category_title} {title}"
        if period and normalize_for_search(period) not in normalize_for_search(title):
            title = f"{title} {period}"
        return title

    def _iter_mziq_documents(self, payload) -> list[dict]:
        """Percorre respostas MZiQ e retorna dicionários que representam documentos."""
        if isinstance(payload, list):
            documents: list[dict] = []
            for item in payload:
                documents.extend(self._iter_mziq_documents(item))
            return documents

        if not isinstance(payload, dict):
            return []

        document_metas = payload.get("document_metas")
        if isinstance(document_metas, list):
            return [item for item in document_metas if isinstance(item, dict)]

        data = payload.get("data")
        if data is not None:
            return self._iter_mziq_documents(data)

        if self._looks_like_mziq_document(payload):
            return [payload]

        documents = []
        for value in payload.values():
            documents.extend(self._iter_mziq_documents(value))
        return documents

    def _looks_like_mziq_document(self, payload: dict) -> bool:
        """Verifica se um dicionário tem campos suficientes de documento MZiQ."""
        has_url = any(payload.get(key) for key in ("link_url", "permalink", "file_url"))
        has_title = any(payload.get(key) for key in ("file_title", "file_name_original"))
        return has_url and has_title

    def _extract_js_assignment(self, html: str, name: str) -> str | None:
        """Extrai `var nome = 'valor'` de blocos JavaScript simples."""
        pattern = re.compile(
            rf"(?:var|let|const)\s+{re.escape(name)}\s*=\s*['\"](?P<value>[^'\"]+)['\"]"
        )
        match = pattern.search(html)
        return match.group("value") if match else None

    def _extract_object_property(self, text: str, name: str) -> str | None:
        """Extrai `nome: 'valor'` de objetos JavaScript literais simples."""
        pattern = re.compile(rf"\b{re.escape(name)}\s*:\s*['\"](?P<value>[^'\"]+)['\"]")
        match = pattern.search(text)
        return match.group("value") if match else None

    def _score_link(self, text: str) -> int:
        """Pontua um link conforme termos relevantes aparecem no texto ou URL."""
        normalized_text = normalize_for_search(text)
        return sum(2 for keyword in KEYWORDS if normalize_for_search(keyword) in normalized_text)
