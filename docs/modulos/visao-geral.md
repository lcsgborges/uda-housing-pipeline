# Visão Geral dos Módulos

| Módulo | Responsabilidade | Principais saídas |
| --- | --- | --- |
| `app/core` | Configuração por `.env`, banco, logging, tempo e normalização textual. | `Settings`, `AsyncSession`, logging configurado. |
| `app/modules/companies` | Cadastro das empresas acompanhadas e URLs de RI. | Empresas ativas para ingestão. |
| `app/modules/ingestion` | Descoberta, download, hash, deduplicação, scheduler e endpoints de lote. | Documentos `downloaded`, `ignored_duplicate` e resumo do ciclo. |
| `app/modules/classification` | Filtro semântico pré-extração. | `classified_useful`, `ignored_not_relevant`, `needs_ocr` ou `failed`. |
| `app/modules/extraction` | Parsing de PDF, full scan/sequential scan, LLM, OpenAI Batch API e persistência. | `metrics`, `document_insights`, `data_lineage` e status `processed`. |
| `app/modules/documents` | Consulta do catálogo de documentos e download/leitura do PDF. | Lista de documentos, metadados e conteúdo quando solicitado. |
| `app/modules/metrics` | Modelo de métricas, catálogo canônico, consulta bruta e endpoint Gold. | `/api/metrics` e `/api/conjuntura`. |
| `app/modules/insights` | Consulta de fatos documentais sem valor numérico obrigatório. | `/api/insights`. |
| `app/modules/lineage` | Registro da origem de cada métrica extraída. | Evidência por documento, página, trecho, modelo e prompt. |
| `app/modules/storage` | Abstração de object storage local ou S3 compatível. | URIs `file://...` ou `s3://...`. |

## Scheduler Interno

Orquestra ingestão de novidades, classificação e extração em lote diariamente
às 02:00 quando `ENABLE_INGESTION_SCHEDULER=true`.

Para entender como esses módulos interagem em tempo de execução, veja
[Operação do Pipeline](../projeto/operacao.md).
