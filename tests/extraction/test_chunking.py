from app.modules.extraction.chunking import SemanticChunker, _numeric_density


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


def test_chunking_marca_pagina_metrica_visual_com_texto_curto():
    chunker = SemanticChunker(max_chars=400)
    pages = ["ROL\nVendas líquidas\nEBITDA\nMargem bruta\n"]

    chunks = chunker.build_chunks(pages)

    assert chunks
    assert "visual_metric_page" in chunks[0].tags
    assert chunks[0].score >= 12


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


def test_select_relevant_chunks_lida_com_lista_vazia_e_preserva_primeiro_relevante():
    chunker = SemanticChunker()
    chunks = chunker.build_chunks(
        [
            "DESEMPENHO OPERACIONAL\nVendas liquidas R$ 100 milhoes",
            "Resultado financeiro com receita liquida, lucro liquido, ebitda e margem bruta.",
        ]
    )

    selected = chunker.select_relevant_chunks(chunks, top_k=1)

    assert chunker.select_relevant_chunks([]) == []
    assert chunks[0] in selected


def test_select_relevant_chunks_default_top_k_aumentado():
    chunker = SemanticChunker()
    chunks = chunker.build_chunks(
        [
            "DESEMPENHO OPERACIONAL\nVendas liquidas R$ 100 milhoes",
            "Resultado financeiro com receita liquida, lucro liquido, ebitda e margem bruta.",
            "Página adicional com ROL e repasses.",
        ]
    )

    selected = chunker.select_relevant_chunks(chunks)

    assert len(selected) <= 20
    assert chunks[0] in selected


def test_split_semantic_blocks_cobre_paginas_vazias_e_titulos_sequenciais():
    chunker = SemanticChunker()

    assert chunker._split_page_into_semantic_blocks("") == []
    assert chunker._split_page_into_semantic_blocks(
        "Texto introdutório\nDESEMPENHO OPERACIONAL\nVendas liquidas"
    ) == [(None, "Texto introdutório"), ("DESEMPENHO OPERACIONAL", "Vendas liquidas")]
    assert chunker._split_page_into_semantic_blocks(
        "DESEMPENHO OPERACIONAL\nRESULTADO FINANCEIRO"
    ) == [(None, "DESEMPENHO OPERACIONAL\nRESULTADO FINANCEIRO")]


def test_heading_rejeita_linhas_longas_numericas_e_numeric_density_vazia():
    chunker = SemanticChunker()

    assert chunker._looks_like_heading("DESEMPENHO OPERACIONAL " * 12) is False
    assert chunker._looks_like_heading("RESULTADO 1234567890") is False
    assert _numeric_density("") == 0.0
