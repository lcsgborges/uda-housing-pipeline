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

Descoberta, download, hash, deduplicação e acionamento da classificação e extração.

## `app/modules/classification`

Filtro semântico pré-extração. Classifica documentos baixados como úteis,
irrelevantes ou dependentes de OCR, salvando motivo, confiança, domínios
detectados e estratégia sugerida.

## `app/modules/extraction`

Parsing de PDFs, chunking, prompt, cliente LLM e persistência de métricas,
insights e linhagem.

## `app/modules/documents`

Consulta do catálogo de documentos e status de processamento.

## `app/modules/metrics`

Modelo das métricas, catálogo canônico, consulta bruta e endpoint de conjuntura.

## `app/modules/insights`

Consulta de fatos documentais extraídos pela LLM, como metas, ações, riscos,
explicações e compromissos que não precisam ter valor numérico explícito.

## `app/modules/lineage`

Registro da origem de cada métrica extraída.

## `app/modules/storage`

Abstração de object storage local ou S3 compatível.

## Scheduler Interno

Orquestra ingestão de novidades, classificação e extração em lote diariamente
às 02:00 quando `ENABLE_INGESTION_SCHEDULER=true`.
