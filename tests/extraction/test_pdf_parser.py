import fitz

from app.modules.extraction.pdf_parser import PDFParser, _extract_page_text


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    content = doc.tobytes()
    doc.close()
    return content


def test_pdf_parser_parse_file_e_bytes(tmp_path):
    content = _make_pdf_bytes("Vendas liquidas R$ 100 milhoes")
    path = tmp_path / "doc.pdf"
    path.write_bytes(content)

    parser = PDFParser()
    parsed_file = parser.parse(str(path))
    parsed_bytes = parser.parse_bytes(content)

    assert parsed_file.pages_count == 1
    assert parsed_bytes.pages_count == 1
    assert parsed_file.pages_text
    assert "Vendas liquidas" in parsed_file.full_text
    assert parsed_file.metadata is not None


def test_extract_page_text_faz_fallback_para_texto_simples():
    class Page:
        def __init__(self):
            self.calls = []

        def get_text(self, kind, sort=False):
            self.calls.append((kind, sort))
            if kind == "blocks":
                return []
            return "texto simples"

    page = Page()

    assert _extract_page_text(page) == "texto simples"
    assert page.calls == [("blocks", True), ("text", False)]
