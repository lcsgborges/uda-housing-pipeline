from app.modules.metrics.catalog import (
    canonical_metric_name,
    find_metric_definition,
    metric_catalog_prompt,
    metric_terms_for_category,
)


def test_catalogo_normaliza_aliases_para_nome_canonico():
    assert canonical_metric_name("Vendas Contratadas Líquidas") == "vendas_liquidas"
    assert canonical_metric_name("Valor Geral de Vendas Lançado") == "vgv_lancado"
    assert canonical_metric_name("Métrica Nova") == "metrica_nova"


def test_catalogo_expoe_metadados_para_extracao_e_chunking():
    definition = find_metric_definition("vendas contratadas liquidas")

    assert definition is not None
    assert definition.name == "vendas_liquidas"
    assert definition.category == "operacional"
    assert "vendas líquidas" in metric_terms_for_category("operacional")
    assert "vendas_liquidas" in metric_catalog_prompt()
