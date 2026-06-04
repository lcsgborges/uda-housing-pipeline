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


def test_chunking_identifica_titulo_e_tags_semanticas():
    chunker = SemanticChunker(max_chars=400)
    pages = [
        """
        DESEMPENHO OPERACIONAL
        Lancamentos 3T25 totalizaram R$ 100 milhoes
        Vendas liquidas atingiram R$ 80 milhoes
        Margem bruta ajustada foi de 32%
        """
    ]

    chunks = chunker.build_chunks(pages)

    assert chunks
    assert chunks[0].heading == "DESEMPENHO OPERACIONAL"
    assert "operacional" in chunks[0].tags
    assert "financeiro" in chunks[0].tags
    assert chunks[0].score > 0


def test_chunking_respeita_orcamento_de_contexto():
    chunker = SemanticChunker(max_chars=120)
    pages = [
        "\n\n".join(
            [
                "RESULTADO OPERACIONAL",
                "Vendas liquidas no trimestre foram de R$ 100 milhoes.",
                "Receita liquida e margem bruta aparecem em tabela.",
                "Texto institucional sem dados relevantes.",
            ]
        )
    ]
    chunks = chunker.build_chunks(pages)
    selected = chunker.select_relevant_chunks(chunks, top_k=5, max_total_chars=150)

    assert selected
    assert sum(len(chunk.text) for chunk in selected) <= 150
