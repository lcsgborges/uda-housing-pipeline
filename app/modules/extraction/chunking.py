import re
from dataclasses import dataclass

from app.core.text import normalize_for_search
from app.modules.metrics.catalog import metric_terms_for_category

SEMANTIC_PROFILES: dict[str, tuple[str, ...]] = {
    "operacional": (
        "operacional",
        "desempenho operacional",
        "lançamento",
        "venda",
        "distrato",
        "vgv",
        "unidade",
        "estoque",
        "landbank",
        "repasse",
        "obra",
        "entrega",
        *metric_terms_for_category("operacional"),
    ),
    "financeiro": (
        "financeiro",
        "desempenho financeiro",
        "receita",
        "lucro",
        "margem",
        "ebitda",
        "caixa",
        "dívida",
        "resultado",
        "patrimônio",
        "roe",
        *metric_terms_for_category("financeiro"),
    ),
    "mercado": (
        "conjuntura habitacional",
        "mercado imobiliário",
        "mercado imobiliario",
        "credito imobiliario",
        "crédito imobiliário",
        "financiamento habitacional",
        "taxa de juros",
        "preço de imóveis",
        "preco de imoveis",
        *metric_terms_for_category("mercado"),
    ),
    "esg": (
        "sustentabilidade",
        "esg",
        "gri",
        "ambiental",
        "indicadores sociais",
        "responsabilidade social",
        "governança",
        "governanca",
        "emissões",
        "emissoes",
        "gases de efeito estufa",
        "gee",
        "co2",
        "energia",
        "água",
        "agua",
        "resíduos",
        "residuos",
        "segurança do trabalho",
        "seguranca do trabalho",
        "diversidade",
        "central de indicadores",
        *metric_terms_for_category("ambiental"),
        *metric_terms_for_category("social"),
    ),
    "periodo": (
        "trimestre",
        "1t",
        "2t",
        "3t",
        "4t",
        "9m",
        "ano",
        "2024",
        "2025",
        "2026",
    ),
    "tabela": (
        "total",
        "comparação",
        "variação",
        "balanço",
        "conjuntura",
        "central de indicadores",
        "x 2t",
        "x 3t",
        "nove meses",
    ),
}

VISUAL_METRIC_TERMS = (
    "rol",
    "receita operacional líquida",
    "receita operacional liquida",
    "vendas líquidas",
    "vendas liquidas",
    "lançamentos",
    "lancamentos",
    "unidades produzidas",
    "margem bruta",
    "ebitda",
    "lucro líquido",
    "lucro liquido",
    "geração de caixa",
    "geracao de caixa",
    "repasses",
    "unidades produzidas",
    "emissões gee",
    "emissoes gee",
    "gases de efeito estufa",
    "consumo de água",
    "consumo de agua",
    "resíduos gerados",
    "residuos gerados",
    "consumo de energia",
    "valor econômico gerado",
    "valor economico gerado",
)

CRITICAL_METRIC_TERMS = (
    "rol",
    "receita operacional líquida",
    "receita operacional liquida",
    "receita líquida",
    "receita liquida",
    "vendas líquidas",
    "vendas liquidas",
    "lançamentos",
    "lancamentos",
    "unidades produzidas",
    "unidades vendidas",
    "margem bruta",
    "ebitda",
    "lucro líquido",
    "lucro liquido",
    "lucro líquido ajustado",
    "lucro liquido ajustado",
    "geração de caixa",
    "geracao de caixa",
    "repasses",
    "venda de ativos",
    "dívida líquida",
    "divida liquida",
    "land bank",
    "vgv",
    "emissões",
    "emissoes",
    "gases de efeito estufa",
    "emissões/up",
    "emissoes/up",
    "consumo de energia",
    "água captada",
    "agua captada",
    "água consumida",
    "agua consumida",
    "descarte de água",
    "descarte de agua",
    "resíduos gerados",
    "residuos gerados",
    "valor econômico gerado",
    "valor economico gerado",
)

LOW_VALUE_CONTEXT_TERMS = (
    "glossario",
    "glossário",
    "aviso",
    "disclaimer",
    "definicoes",
    "definições",
)


@dataclass(frozen=True)
class Chunk:
    page: int
    text: str
    score: int
    ordinal: int
    heading: str | None = None
    tags: tuple[str, ...] = ()


class SemanticChunker:
    """Builds semantic chunks for retrieval, not rule-based metric extraction."""

    def __init__(self, max_chars: int = 2200, overlap_chars: int = 240):
        """Configura limites de tamanho e sobreposição entre chunks."""
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def build_chunks(self, pages_text: list[str]) -> list[Chunk]:
        """Transforma textos por página em chunks ranqueados e anotados."""
        chunks: list[Chunk] = []
        ordinal = 0
        for page_index, page_text in enumerate(pages_text, start=1):
            for heading, block in self._split_page_into_semantic_blocks(page_text):
                for text in self._bound_block(block):
                    tags = self._tags_for(text, heading=heading)
                    score = self._score_chunk(text, heading=heading, tags=tags)
                    chunks.append(
                        Chunk(
                            page=page_index,
                            text=text,
                            score=score,
                            ordinal=ordinal,
                            heading=heading,
                            tags=tags,
                        )
                    )
                    ordinal += 1
        return chunks

    def select_relevant_chunks(
        self,
        chunks: list[Chunk],
        top_k: int = 20,
        max_total_chars: int | None = None,
    ) -> list[Chunk]:
        """Seleciona os chunks mais relevantes respeitando orçamento opcional."""
        if not chunks:
            return []

        ranked = sorted(chunks, key=lambda c: (c.score, -c.ordinal), reverse=True)
        selected = ranked[:top_k]

        first_chunk = chunks[0]
        if first_chunk.score > 0 and first_chunk not in selected:
            selected.append(first_chunk)

        selected = sorted(set(selected), key=lambda c: c.ordinal)
        if max_total_chars is None:
            return selected

        bounded: list[Chunk] = []
        budget = 0
        for chunk in selected:
            chunk_size = len(chunk.text)
            if bounded and budget + chunk_size > max_total_chars:
                continue
            bounded.append(chunk)
            budget += chunk_size
            if budget >= max_total_chars:
                break
        return bounded or selected[:1]

    def _split_page_into_semantic_blocks(self, text: str) -> list[tuple[str | None, str]]:
        """Divide uma página em blocos associados a possíveis headings."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return []

        blocks: list[tuple[str | None, str]] = []
        heading: str | None = None
        current: list[str] = []

        for line in lines:
            if self._looks_like_heading(line):
                if current:
                    blocks.append((heading, "\n".join(current)))
                    current = []
                heading = line
                continue
            current.append(line)

        if current:
            blocks.append((heading, "\n".join(current)))

        if not blocks:
            return [(None, "\n".join(lines))]
        return blocks

    def _bound_block(self, text: str) -> list[str]:
        """Quebra um bloco textual em pedaços dentro do limite de caracteres."""
        if len(text) <= self.max_chars:
            return [text]

        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        if len(paragraphs) <= 1:
            paragraphs = [line.strip() for line in text.splitlines() if line.strip()]

        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 2 <= self.max_chars:
                current = f"{current}\n{paragraph}".strip()
                continue
            if current:
                chunks.append(current)
            overlap = current[-self.overlap_chars :] if current else ""
            current = f"{overlap}\n{paragraph}".strip() if overlap else paragraph

        if current:
            chunks.append(current[: self.max_chars])
        return chunks

    def _looks_like_heading(self, line: str) -> bool:
        """Identifica se uma linha tem aparência e conteúdo de título semântico."""
        normalized = _normalize(line)
        if len(line) > 90 or len(line.split()) > 10:
            return False
        if _numeric_density(line) > 0.25:
            return False
        has_semantic_term = any(
            _normalize(term) in normalized for terms in SEMANTIC_PROFILES.values() for term in terms
        )
        is_visual_heading = line.isupper() or line.istitle() or normalized.endswith(":")
        return has_semantic_term and is_visual_heading

    def _tags_for(self, text: str, heading: str | None = None) -> tuple[str, ...]:
        """Atribui tags semânticas a partir de termos presentes no bloco."""
        normalized = _normalize(f"{heading or ''}\n{text}")
        tags = [
            tag
            for tag, terms in SEMANTIC_PROFILES.items()
            if any(_normalize(term) in normalized for term in terms)
        ]
        if any(_normalize(term) in normalized for term in VISUAL_METRIC_TERMS):
            tags.append("visual_metric_page")
        if any(_normalize(term) in normalized for term in CRITICAL_METRIC_TERMS):
            tags.append("metricas_criticas")
        if _has_table_shape(text):
            tags.append("tabela")
        return tuple(sorted(set(tags)))

    def _score_chunk(self, text: str, *, heading: str | None, tags: tuple[str, ...]) -> int:
        """Pontua um chunk pela presença de termos, tabelas e valores monetários."""
        normalized = _normalize(f"{heading or ''}\n{text}")
        score = 0
        for tag, terms in SEMANTIC_PROFILES.items():
            hits = sum(1 for term in terms if _normalize(term) in normalized)
            weight = 3 if tag in {"operacional", "financeiro"} else 2
            score += hits * weight
        score += len(tags) * 2
        visual_hits = sum(1 for term in VISUAL_METRIC_TERMS if _normalize(term) in normalized)
        score += visual_hits * 12
        critical_hits = sum(1 for term in CRITICAL_METRIC_TERMS if _normalize(term) in normalized)
        score += critical_hits * 8
        if critical_hits and _has_numeric_signal(text):
            score += 10
        if _has_table_shape(text):
            score += 5
        if "%" in text or "r$" in normalized or "brl" in normalized:
            score += 3
        if _is_low_value_context(text, heading=heading):
            score -= 90
            if not _has_numeric_signal(text):
                score -= 60
        return score


def _normalize(value: str) -> str:
    """Normaliza texto para comparação sem acento e sem diferença de caixa."""
    return normalize_for_search(value)


def _numeric_density(value: str) -> float:
    """Calcula a proporção de caracteres numéricos em um texto."""
    if not value:
        return 0.0
    return sum(char.isdigit() for char in value) / len(value)


def _has_table_shape(value: str) -> bool:
    """Detecta forma tabular simples por linhas com números ou percentuais."""
    lines = [line for line in value.splitlines() if line.strip()]
    numeric_lines = sum(1 for line in lines if any(char.isdigit() for char in line))
    percent_lines = sum(1 for line in lines if "%" in line)
    return len(lines) >= 3 and (numeric_lines >= 2 or percent_lines >= 2)


def _has_numeric_signal(value: str) -> bool:
    """Detecta se o texto contém sinais numéricos relevantes para métricas."""
    normalized = _normalize(value)
    return bool(
        re.search(
            r"\d+[,.]?\d*\s*(%|p\.p\.|milhões|milhoes|bilhões|bilhoes|k|mm|r\$|us\$|m3|tco2e)",
            normalized,
        )
        or re.search(r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b", normalized)
    )


def _is_low_value_context(text: str, *, heading: str | None) -> bool:
    """Identifica blocos ricos em termos, mas pobres como evidência numérica."""
    normalized = _normalize(f"{heading or ''}\n{text}")
    return any(_normalize(term) in normalized for term in LOW_VALUE_CONTEXT_TERMS)
