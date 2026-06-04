# Visão Geral dos Módulos

## `app/core`

Base comum da aplicação:

- configuração por `.env`;
- engine SQLAlchemy;
- sessão de banco;
- logging;
- funções de tempo e normalização textual.

## `app/modules/companies`

Cadastro das empresas acompanhadas e suas URLs de RI.

## `app/modules/ingestion`

Descoberta, download, hash, deduplicação e acionamento da extração.

## `app/modules/extraction`

Parsing de PDFs, chunking, prompt, cliente LLM e persistência do resultado extraído.

## `app/modules/documents`

Consulta do catálogo de documentos e status de processamento.

## `app/modules/metrics`

Modelo das métricas, catálogo canônico, consulta bruta e endpoint de conjuntura.

## `app/modules/lineage`

Registro da origem de cada métrica extraída.

## `app/modules/storage`

Abstração de object storage local ou S3 compatível.

## Scheduler Interno

Orquestra ingestão de novidades e extração em lote diariamente às 02:00 quando
`ENABLE_INGESTION_SCHEDULER=true`.
