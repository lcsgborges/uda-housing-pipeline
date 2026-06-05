# Insights Documentais

## Responsabilidade

Insights documentais guardam informações úteis que não precisam ser uma métrica numérica. Eles complementam a tabela `metrics` com fatos, metas, riscos, ações, compromissos, explicações de desempenho e evidências qualitativas.

## Quando Um Insight é Criado

Durante a extração, a LLM pode retornar `insights` junto com `metrics`. Cada insight passa pelo contrato Pydantic `ExtractedInsight` e é persistido em `document_insights`.

Use insights quando:

- há uma meta ou compromisso sem valor numérico final;
- existe uma ação realizada ou planejada;
- o documento explica causas de uma variação;
- há risco, oportunidade, certificação, política ou governança relevante;
- o dado é textual, mas ainda é importante para análise de conjuntura.

## Campos Persistidos

| Campo | Significado |
| --- | --- |
| `insight_type` | Tipo em `snake_case`, como `meta`, `risco`, `acao` ou `explicacao`. |
| `topic` | Tópico canônico em `snake_case`. |
| `summary` | Resumo do fato documental. |
| `value_text` | Valor textual opcional, quando houver. |
| `period_year` e `period_quarter` | Período de referência, quando inferido. |
| `source_page` e `source_excerpt` | Evidência original do PDF. |
| `confidence` | Confiança entre `0` e `1`. |

## Consulta

```http
GET /api/insights
GET /api/insights?empresa=MRV&ano=2025
GET /api/insights?document_id=10&tipo=risco
GET /api/insights?topico=sustentabilidade
```

O serviço resolve `empresa` por nome ou ticker. Se a empresa informada não existir, a lista retornada é vazia.

## Diferença Para Métricas

Métricas exigem `value` numérico explícito para entrar em `metrics`. Insights não exigem valor numérico, mas precisam ter resumo, tipo, tópico e confiança válidos pelo contrato Pydantic.
