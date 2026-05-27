from app.modules.extraction.chunking import SemanticChunker


def test_chunking_prioriza_palavras_chave():
    chunker = SemanticChunker(max_chars=200)
    pages = [
        "Texto institucional.",
        "Vendas líquidas no trimestre foram de R$ 100 milhões.\n\nMargem bruta em evolução.",
    ]
    chunks = chunker.build_chunks(pages)
    selected = chunker.select_relevant_chunks(chunks, top_k=1)
    assert selected
    assert "vendas líquidas" in selected[0].text.lower()
