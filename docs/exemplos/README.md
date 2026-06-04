# Exemplos de dados

## Boletim de conjuntura 3T2025

O arquivo `conjuntura_3t2025_exemplo.json` transcreve a imagem de exemplo enviada para um formato estruturado de referência.

Mapeamento recomendado para a tabela `metrics`:

- `metric_group`: base do nome da métrica (`lancamentos` ou `vendas`);
- chaves de comparação (`x_2t25`, `x_3t24`, `nove_meses_24_23`, `nove_meses_25_24`): sufixos do `metric_name`;
- valor numérico: campo `value`;
- unidade: `%`;
- empresa: `company`;
- período principal do boletim: `period_year=2025`, `period_quarter=3`;
- fonte/linhagem: documento original, página e trecho de onde a tabela saiu.

Exemplo de métrica derivada para a API:
```json
{
  "company": "MRV",
  "period_year": 2025,
  "period_quarter": 3,
  "metric_name": "lancamentos_variacao_x_2t25",
  "metric_category": "comparativo",
  "value": -32,
  "unit": "%",
  "currency": null,
  "source_page": 1,
  "source_excerpt": "MRV: Lançamentos 3T25 x 2T25 = -32%",
  "confidence": 0.95
}
```

Para relatórios de RI das empresas, o contrato semântico continua priorizando valores absolutos. Para boletins/tabelas comparativas, percentuais são dados válidos quando forem o valor principal publicado.
