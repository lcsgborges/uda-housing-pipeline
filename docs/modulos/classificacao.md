# Módulo de Classificação

## Responsabilidade

O módulo de classificação decide se um PDF baixado deve seguir para extração completa. Ele existe para reduzir custo, latência e ruído, porque nem todo PDF encontrado em uma página de RI contém métricas úteis.

## Componentes

| Arquivo | Responsabilidade |
| --- | --- |
| `app/modules/classification/service.py` | Orquestra leitura do PDF, montagem de contexto, chamada da LLM e transição de status. |
| `app/modules/classification/schemas.py` | Define o contrato `DocumentClassification`. |
| `app/modules/extraction/pdf_parser.py` | Extrai texto por página usando PyMuPDF. |
| `app/modules/extraction/chunking.py` | Reaproveitado para montar amostras relevantes de documentos longos. |
| `app/modules/extraction/llm_client.py` | Implementa a chamada de classificação para Ollama ou OpenAI. |

## Fluxo

1. Seleciona documentos com status `downloaded`.
2. Marca o documento como `classifying`.
3. Lê o PDF por arquivo local, `file://`, `rustfs://` ou `s3://`.
4. Extrai texto com PyMuPDF.
5. Se o texto for insuficiente, classifica de forma determinística como `needs_ocr`.
6. Se houver texto, monta uma amostra com páginas iniciais e chunks ranqueados.
7. Envia a amostra para a LLM com o contrato `DocumentClassification`.
8. Persiste decisão, confiança, motivo, domínios detectados e estratégia de extração.

## Contrato

`DocumentClassification` contém:

- `is_useful`: indica se há dados úteis para extração.
- `document_type`: tipo em `snake_case`, como `resultado_trimestral` ou `relatorio_sustentabilidade`.
- `domains`: domínios detectados, como financeiro, operacional, ESG ou mercado.
- `year` e `quarter`: período quando houver evidência.
- `extraction_strategy`: `full_scan`, `sequential_scan`, `ignore` ou `needs_ocr`.
- `reason`: justificativa curta.
- `confidence`: confiança entre `0` e `1`.

O valor legado `semantic_chunking` ainda é aceito pelo contrato para compatibilidade com classificações antigas, mas a extração atual usa varredura sequencial completa para documentos longos.

## Estados Gerados

| Estratégia/decisão | Status persistido |
| --- | --- |
| Útil para extração | `classified_useful` |
| Irrelevante ou `ignore` | `ignored_not_relevant` |
| Texto insuficiente ou PDF escaneado | `needs_ocr` |
| Exceção de leitura, storage ou LLM | `failed` |

## Processamento em Lote

O endpoint de lote usa `ClassificationService.process_pending_documents_batch()`:

```http
POST /api/ingestion/classify-batch?batch_size=5
```

O retorno resume `selected`, `useful`, `ignored`, `needs_ocr` e `failed`. O ciclo completo de ingestão também chama `process_all_pending_documents()` antes da extração.
