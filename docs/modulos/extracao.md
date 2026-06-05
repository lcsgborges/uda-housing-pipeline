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
5. Montar contexto completo para PDFs curtos ou partes sequenciais para PDFs longos.
6. Enviar cada contexto pequeno para a LLM.
7. Consolidar métricas e insights retornados pelas partes.
8. Validar resposta por Pydantic.
9. Normalizar métrica por catálogo.
10. Persistir `metrics`, `document_insights` e `data_lineage`.
11. Marcar documento como `processed` ou `failed`.

## Full Scan vs Varredura Sequencial

| Modo | Quando Usa | Observação |
| --- | --- | --- |
| `full_scan` | Documento abaixo de `EXTRACTION_FULL_SCAN_MAX_CHARS` | Envia o texto inteiro. |
| `sequential_scan` | Documento longo | Divide o texto em partes sequenciais de até `EXTRACTION_CONTEXT_MAX_CHARS` e envia todas as partes. |

Em documentos longos, a extração não descarta páginas menos ranqueadas. O serviço percorre o texto completo, respeitando a ordem das páginas, e faz várias chamadas menores à LLM. Depois remove duplicidades exatas de métricas e insights antes de persistir.

Se uma parte falhar por erro de LLM ou contrato, o documento recebe `failed`, porque a extração não pode afirmar que analisou o documento inteiro. Partes sem métricas ou insights são aceitas quando outras partes do mesmo documento retornam dados úteis.

## Cliente LLM

Há dois provedores:

- `ollama`: extração local, documento a documento, sem API externa.
- `openai`: extração remota via OpenAI Responses API.

Há dois modos de extração com OpenAI:

- síncrono: `POST /api/ingestion/extract-batch`, útil para poucos documentos ou validação manual;
- assíncrono com desconto: OpenAI Batch API, usando arquivo JSONL, `purpose=batch`, endpoint `/v1/responses` e janela `24h`.

No modo assíncrono, o sistema:

1. Seleciona documentos em `classified_useful`.
2. Divide documentos longos em partes sequenciais.
3. Cria uma linha JSONL por parte, com `custom_id` no formato `document-{id}-part-{n}-of-{total}`.
4. Envia o arquivo pela Files API com `purpose=batch`.
5. Cria o batch no endpoint `/v1/responses`.
6. Consulta o status até `completed`.
7. Baixa `output_file_id`, agrupa as partes por documento, valida `ExtractedMetricBatch` e persiste métricas/insights.

O parâmetro `batch_size` controla quantos documentos são selecionados do banco para submissão. O número real de requests no arquivo JSONL pode ser maior, porque cada documento longo gera várias partes.

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

Para extração em lote, o contrato externo é `ExtractedBatchResponse`, com uma lista `documents`. Cada item precisa copiar o `document_ref` recebido no prompt. Em varredura sequencial, o `document_ref` inclui a parte (`id:part:n`) para rastrear cada payload.

## Retentativa Individual

Quando a chamada de lote não retorna um documento, ou retorna métricas e insights vazios, `ExtractionService` tenta uma extração individual para aquele payload. Se a retentativa também não produzir dados, o documento recebe `failed` e uma `error_message`.

No fluxo OpenAI Batch API, a importação é deliberadamente conservadora: se alguma parte de um documento retornar erro, ou se o output não trouxer todas as partes esperadas pelo `custom_id`, o documento fica `failed`.

## Endpoints Batch API

```http
POST /api/ingestion/openai-batch/submit?batch_size=1
GET /api/ingestion/openai-batch/{batch_id}
POST /api/ingestion/openai-batch/{batch_id}/import
```

Use `submit` para criar o arquivo JSONL e o batch, `GET` para acompanhar status, e `import` apenas depois que o status estiver `completed`.

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
