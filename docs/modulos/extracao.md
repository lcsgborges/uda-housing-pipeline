# Módulo de Extração UDA

## Responsabilidade

Extrair métricas estruturadas e insights documentais de PDFs classificados como úteis.

## Estratégia

O módulo evita regex para extração final de valores. Regras tradicionais aparecem apenas para preparar o contexto, controlar tamanho e melhorar custo/latência.

## Etapas

1. Selecionar documentos em `classified_useful`.
2. Marcar documentos do lote como `processing`.
3. Ler PDF de storage local ou S3.
4. Extrair texto por página.
5. Montar contexto completo ou chunks semânticos.
6. Enviar contexto para LLM.
7. Validar resposta por Pydantic.
8. Normalizar métrica por catálogo.
9. Persistir `metrics`, `document_insights` e `data_lineage`.
10. Marcar documento como `processed` ou `failed`.

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
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1
```

Em execução sem Docker, use `OLLAMA_BASE_URL=http://localhost:11434`.

Modelos de classificação podem ser configurados separadamente:

```env
OPENAI_CLASSIFICATION_MODEL=gpt-4.1-mini
OLLAMA_CLASSIFICATION_MODEL=llama3.1
```

## Contrato Semântico

A saída deve seguir:

- `metrics`
- `insights`
- `company`, dentro de cada métrica
- `period_year`
- `period_quarter`
- `period_label`
- `metric_name`
- `metric_category`
- `raw_label`
- `dimension`
- `value`
- `unit`
- `currency`
- `source_page`
- `source_excerpt`
- `confidence`

Para extração em lote, o contrato externo é `ExtractedBatchResponse`, com uma lista `documents`. Cada item precisa copiar o `document_ref` recebido no prompt.

## Retentativa Individual

Quando a chamada de lote não retorna um documento, ou retorna métricas e insights vazios, `ExtractionService` tenta uma extração individual para aquele payload. Se a retentativa também não produzir dados, o documento recebe `failed` e uma `error_message`.

## Insights

Quando uma informação é útil, mas não tem valor numérico explícito, a LLM deve preencher `insights`. Exemplos: metas, compromissos, riscos, explicações de desempenho, certificações e ações ESG.

## Catálogo de Métricas

O catálogo em `app/modules/metrics/catalog.py` reduz variação de nomes e define metadados esperados.

Exemplos:

| Alias | Nome Canônico |
| --- | --- |
| `vendas contratadas líquidas` | `vendas_liquidas` |
| `valor geral de vendas lançado` | `vgv_lancado` |
| `dívida líquida` | `divida_liquida` |
