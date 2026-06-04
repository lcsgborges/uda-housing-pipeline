# Módulo de Extração UDA

## Responsabilidade

Extrair métricas estruturadas de documentos não estruturados.

## Estratégia

O módulo evita regex para extração final de valores. Regras tradicionais aparecem apenas para preparar o contexto, controlar tamanho e melhorar custo/latência.

## Etapas

1. Ler PDF de storage local ou S3.
2. Extrair texto por página.
3. Montar contexto completo ou chunks semânticos.
4. Enviar contexto para LLM.
5. Validar resposta por Pydantic.
6. Normalizar métrica por catálogo.
7. Persistir `metrics` e `data_lineage`.

## Full Scan vs Chunking

| Modo | Quando Usa | Observação |
| --- | --- | --- |
| `full_scan` | Documento abaixo de `EXTRACTION_FULL_SCAN_MAX_CHARS` | Envia o texto inteiro. |
| `semantic_chunking` | Documento longo | Seleciona chunks por score semântico. |

## Cliente LLM

Há dois provedores:

- `ollama`: extração local, documento a documento, sem API externa.
- `openai`: extração remota via OpenAI Responses API, agrupando documentos por lote.

Configuração:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

## Contrato Semântico

A saída deve seguir:

- `company`
- `period_year`
- `period_quarter`
- `metric_name`
- `metric_category`
- `value`
- `unit`
- `currency`
- `source_page`
- `source_excerpt`
- `confidence`

## Catálogo de Métricas

O catálogo em `app/modules/metrics/catalog.py` reduz variação de nomes e define metadados esperados.

Exemplos:

| Alias | Nome Canônico |
| --- | --- |
| `vendas contratadas líquidas` | `vendas_liquidas` |
| `valor geral de vendas lançado` | `vgv_lancado` |
| `dívida líquida` | `divida_liquida` |
