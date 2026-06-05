import re
from dataclasses import dataclass

from app.core.text import normalize_for_search


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    category: str
    aliases: tuple[str, ...]
    default_unit: str | None = None
    default_currency: str | None = None
    priority: int = 100


METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        name="vendas_liquidas",
        category="operacional",
        aliases=(
            "vendas liquidas",
            "vendas líquidas",
            "vendas contratadas liquidas",
            "vendas contratadas líquidas",
            "vendas liquidas contratadas",
            "vendas líquidas contratadas",
        ),
        default_unit="R$",
        default_currency="BRL",
        priority=10,
    ),
    MetricDefinition(
        name="vgv_lancado",
        category="operacional",
        aliases=(
            "vgv lancado",
            "vgv lançado",
            "valor geral de vendas lancado",
            "valor geral de vendas lançado",
            "lancamentos em vgv",
            "lançamentos em vgv",
        ),
        default_unit="R$",
        default_currency="BRL",
        priority=20,
    ),
    MetricDefinition(
        name="lancamentos",
        category="operacional",
        aliases=("lancamentos", "lançamentos", "unidades lancadas", "unidades lançadas"),
        priority=30,
    ),
    MetricDefinition(
        name="unidades_vendidas",
        category="operacional",
        aliases=("unidades vendidas", "vendas em unidades", "unidades comercializadas"),
        priority=40,
    ),
    MetricDefinition(
        name="unidades_produzidas",
        category="operacional",
        aliases=("unidades produzidas", "producao em unidades", "produção em unidades"),
        priority=45,
    ),
    MetricDefinition(
        name="distratos",
        category="operacional",
        aliases=("distratos", "cancelamentos", "vendas distratadas"),
        priority=50,
    ),
    MetricDefinition(
        name="estoque",
        category="operacional",
        aliases=("estoque", "estoque a valor de mercado", "estoque pronto"),
        default_unit="R$",
        default_currency="BRL",
        priority=60,
    ),
    MetricDefinition(
        name="landbank",
        category="operacional",
        aliases=("landbank", "banco de terrenos", "estoque de terrenos"),
        default_unit="R$",
        default_currency="BRL",
        priority=70,
    ),
    MetricDefinition(
        name="receita_liquida",
        category="financeiro",
        aliases=("receita liquida", "receita líquida", "receita operacional liquida"),
        default_unit="R$",
        default_currency="BRL",
        priority=80,
    ),
    MetricDefinition(
        name="lucro_liquido",
        category="financeiro",
        aliases=("lucro liquido", "lucro líquido", "resultado liquido", "resultado líquido"),
        default_unit="R$",
        default_currency="BRL",
        priority=90,
    ),
    MetricDefinition(
        name="ebitda",
        category="financeiro",
        aliases=("ebitda", "lajida"),
        default_unit="R$",
        default_currency="BRL",
        priority=100,
    ),
    MetricDefinition(
        name="margem_bruta",
        category="financeiro",
        aliases=("margem bruta",),
        default_unit="%",
        priority=110,
    ),
    MetricDefinition(
        name="margem_ebitda",
        category="financeiro",
        aliases=("margem ebitda", "margem lajida"),
        default_unit="%",
        priority=120,
    ),
    MetricDefinition(
        name="divida_liquida",
        category="financeiro",
        aliases=("divida liquida", "dívida líquida", "endividamento liquido"),
        default_unit="R$",
        default_currency="BRL",
        priority=130,
    ),
    MetricDefinition(
        name="caixa",
        category="financeiro",
        aliases=("caixa", "disponibilidades", "caixa e equivalentes"),
        default_unit="R$",
        default_currency="BRL",
        priority=140,
    ),
    MetricDefinition(
        name="repasse",
        category="financeiro",
        aliases=("repasse", "repasses", "financiamento bancario", "financiamento bancário"),
        default_unit="R$",
        default_currency="BRL",
        priority=150,
    ),
    MetricDefinition(
        name="geracao_caixa",
        category="financeiro",
        aliases=("geracao de caixa", "geração de caixa", "cash generation"),
        default_unit="R$",
        default_currency="BRL",
        priority=155,
    ),
    MetricDefinition(
        name="entregas",
        category="operacional",
        aliases=("entregas", "unidades entregues", "empreendimentos entregues"),
        priority=160,
    ),
    MetricDefinition(
        name="credito_imobiliario",
        category="mercado",
        aliases=("credito imobiliario", "crédito imobiliário", "financiamento imobiliario"),
        default_unit="R$",
        default_currency="BRL",
        priority=170,
    ),
    MetricDefinition(
        name="taxa_juros_imobiliario",
        category="mercado",
        aliases=("taxa de juros imobiliario", "taxa de juros imobiliário", "juros habitacionais"),
        default_unit="%",
        priority=180,
    ),
    MetricDefinition(
        name="indice_preco_imoveis",
        category="mercado",
        aliases=("indice de preco de imoveis", "índice de preço de imóveis", "preco de imoveis"),
        default_unit="%",
        priority=190,
    ),
    MetricDefinition(
        name="emissoes_gee",
        category="ambiental",
        aliases=(
            "emissoes gee",
            "emissões gee",
            "emissoes de gases de efeito estufa",
            "emissões de gases de efeito estufa",
            "emissoes de co2",
            "emissões de co2",
        ),
        default_unit="tCO2e",
        priority=200,
    ),
    MetricDefinition(
        name="emissoes_gee_por_unidade_produzida",
        category="ambiental",
        aliases=(
            "emissoes por unidade produzida",
            "emissões por unidade produzida",
            "emissoes/up",
            "emissões/up",
        ),
        default_unit="tCO2e/unidade",
        priority=210,
    ),
    MetricDefinition(
        name="consumo_energia",
        category="ambiental",
        aliases=("consumo de energia", "energia consumida", "energia elétrica consumida"),
        priority=220,
    ),
    MetricDefinition(
        name="energia_renovavel",
        category="ambiental",
        aliases=("energia renovavel", "energia renovável", "fontes renovaveis"),
        default_unit="%",
        priority=230,
    ),
    MetricDefinition(
        name="agua_captada",
        category="ambiental",
        aliases=("agua captada", "água captada", "captacao de agua", "captação de água"),
        default_unit="m3",
        priority=240,
    ),
    MetricDefinition(
        name="agua_consumida",
        category="ambiental",
        aliases=("agua consumida", "água consumida", "consumo de agua", "consumo de água"),
        default_unit="m3",
        priority=250,
    ),
    MetricDefinition(
        name="agua_descartada",
        category="ambiental",
        aliases=("agua descartada", "água descartada", "descarte de agua", "descarte de água"),
        default_unit="m3",
        priority=260,
    ),
    MetricDefinition(
        name="residuos_gerados",
        category="ambiental",
        aliases=("residuos gerados", "resíduos gerados", "geracao de residuos"),
        priority=270,
    ),
    MetricDefinition(
        name="residuos_reciclados",
        category="ambiental",
        aliases=("residuos reciclados", "resíduos reciclados", "reciclagem de residuos"),
        default_unit="%",
        priority=280,
    ),
    MetricDefinition(
        name="colaboradores",
        category="social",
        aliases=("colaboradores", "empregados", "funcionarios", "funcionários"),
        priority=290,
    ),
    MetricDefinition(
        name="mulheres_lideranca",
        category="social",
        aliases=("mulheres na lideranca", "mulheres na liderança", "lideranca feminina"),
        default_unit="%",
        priority=300,
    ),
    MetricDefinition(
        name="taxa_frequencia_acidentes",
        category="social",
        aliases=(
            "taxa de frequencia de acidentes",
            "taxa de frequência de acidentes",
            "frequencia de acidentes",
        ),
        priority=310,
    ),
    MetricDefinition(
        name="valor_economico_gerado",
        category="financeiro",
        aliases=("valor economico gerado", "valor econômico gerado", "gri 201-1"),
        default_unit="R$",
        default_currency="BRL",
        priority=320,
    ),
)


def _to_snake_case(value: str) -> str:
    """Normaliza texto livre para snake_case sem acentos."""
    normalized = normalize_for_search(value)
    slug = re.sub(r"[^a-z0-9]+", "_", normalized)
    return re.sub(r"_+", "_", slug).strip("_")


_DEFINITIONS_BY_NAME = {definition.name: definition for definition in METRIC_DEFINITIONS}
_ALIASES_BY_SLUG = {
    _to_snake_case(alias): definition.name
    for definition in METRIC_DEFINITIONS
    for alias in (definition.name, *definition.aliases)
}


def canonical_metric_name(value: str) -> str:
    """Resolve aliases conhecidos para o nome canônico da métrica."""
    slug = _to_snake_case(value)
    return _ALIASES_BY_SLUG.get(slug, slug)


def find_metric_definition(value: str) -> MetricDefinition | None:
    """Busca a definição de catálogo para uma métrica ou alias."""
    return _DEFINITIONS_BY_NAME.get(canonical_metric_name(value))


def metric_terms_for_category(category: str) -> tuple[str, ...]:
    """Retorna termos e aliases usados para ranquear chunks por categoria."""
    terms: list[str] = []
    for definition in METRIC_DEFINITIONS:
        if definition.category != category:
            continue
        terms.append(definition.name.replace("_", " "))
        terms.extend(definition.aliases)
    return tuple(dict.fromkeys(terms))


def metric_catalog_prompt() -> str:
    """Renderiza o catálogo de métricas em texto para o prompt da LLM."""
    lines = [
        (
            f"- {definition.name}: categoria={definition.category}, "
            f"aliases={', '.join(definition.aliases[:3])}"
        )
        for definition in METRIC_DEFINITIONS
    ]
    return "\n".join(lines)


def metric_priority(value: str) -> int:
    """Retorna a prioridade de ordenação da métrica no catálogo."""
    definition = find_metric_definition(value)
    return definition.priority if definition else 999
