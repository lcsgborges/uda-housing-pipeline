from app.modules.metrics.catalog import (
    canonical_metric_name,
    find_metric_definition,
    metric_catalog_prompt,
    metric_terms_for_category,
)


def test_catalogo_normaliza_aliases_para_nome_canonico():
    """Valida normalização de aliases para nomes canônicos."""
    assert canonical_metric_name("Vendas Contratadas Líquidas") == "vendas_liquidas"
    assert canonical_metric_name("Valor Geral de Vendas Lançado") == "vgv_lancado"
    assert canonical_metric_name("Métrica Nova") == "metrica_nova"


def test_catalogo_expoe_metadados_para_extracao_e_chunking():
    """Valida metadados do catálogo usados por extração e chunking."""
    definition = find_metric_definition("vendas contratadas liquidas")
    esg_definition = find_metric_definition("emissões de gases de efeito estufa")

    assert definition is not None
    assert definition.name == "vendas_liquidas"
    assert definition.category == "operacional"
    assert esg_definition is not None
    assert esg_definition.name == "emissoes_gee"
    assert "vendas líquidas" in metric_terms_for_category("operacional")
    assert "emissões gee" in metric_terms_for_category("ambiental")
    assert "vendas_liquidas" in metric_catalog_prompt()
