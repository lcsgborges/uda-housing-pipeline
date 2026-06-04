# Pipeline UDA - Análise de Dados Não Estruturados

Pipeline backend para coletar PDFs de Relações com Investidores, extrair métricas semânticas com LLM, validar via contrato Pydantic e disponibilizar dados estruturados para relatórios de conjuntura habitacional.

## Objetivo

Transformar documentos não estruturados (PDFs de resultados/prévias operacionais) em dados relacionais rastreáveis por linhagem, com API REST para consulta por empresa, ano e trimestre.

## Arquitetura

- `app/core`: configuração, logging e banco.
- `app/modules/companies`: cadastro e gestão de empresas/fonte RI.
- `app/modules/ingestion`: scraping, download, hash, idempotência e gatilho de ingestão.
- `app/modules/extraction`: parsing de PDF, chunking semântico, cliente LLM e orquestração de extração.
- `app/modules/documents`: catálogo de documentos e status de processamento.
- `app/modules/metrics`: métricas extraídas e endpoint de conjuntura.
- `app/modules/lineage`: rastreabilidade origem -> métrica.
- `alembic`: migrations de schema.
- `tests`: testes unitários e de API.

## Tecnologias

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL via `asyncpg`
- Pydantic v2 + pydantic-settings
- PyMuPDF
- httpx + BeautifulSoup4
- OpenAI SDK via Responses API e contrato Pydantic
- RustFS como object storage S3-compatible
- pytest + Testcontainers para banco PostgreSQL nos testes
- Ruff

## Instalação

```bash
uv sync --extra dev
```

## Configuração `.env`

```bash
cp .env.example .env
```

Variáveis principais:

- `DATABASE_URL=postgresql+asyncpg://uda:uda@localhost:5432/uda`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` para o Compose
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY` para extração real via API da OpenAI
- `LLM_PROVIDER=fake` para modo de desenvolvimento sem chave/custo de API
- `OPENAI_MODEL=gpt-4.1-mini`
- `DOCUMENTS_DIR=./data/documents`
- `STORAGE_BACKEND=local|rustfs`
- `RUSTFS_ENDPOINT`, `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, `RUSTFS_BUCKET`
- `EXTRACTION_BATCH_SIZE=5`
- `ENABLE_INGESTION_SCHEDULER=true` para observação contínua
- `INGESTION_POLL_INTERVAL_MINUTES=1440` (1x/dia)

## Executar com Docker Compose

Configure a chave da OpenAI no ambiente ou no arquivo `.env`:

```bash
cp .env.example .env
```

Edite `.env` e preencha:

```bash
OPENAI_API_KEY=sk-...
```

Suba API + PostgreSQL + RustFS:

```bash
docker compose --env-file .env up --build
```

Serviços:

- API: `http://localhost:8000`
- Swagger/OpenAPI: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- RustFS S3 API: `http://localhost:9000`
- RustFS Console: `http://localhost:9001`

O compose usa PostgreSQL para o catálogo relacional, `STORAGE_BACKEND=rustfs` e grava objetos no bucket `uda-documents`.

## Executar servidor

```bash
uv run uvicorn app.main:app --reload
```

## Rodar migrations

```bash
uv run alembic upgrade head
```

## Rodar ingestão

- Via CLI:

```bash
uv run python -m app.modules.ingestion.scheduler
```

Com scheduler contínuo no servidor:

```bash
ENABLE_INGESTION_SCHEDULER=true uv run uvicorn app.main:app --reload
```

- Via API:

```http
POST /api/ingestion/run
POST /api/ingestion/run/{company_id}
POST /api/ingestion/extract-batch?batch_size=10
```

## Rodar testes

Os testes sobem um PostgreSQL efêmero via Testcontainers. Docker precisa estar disponível.

```bash
uv run --extra dev pytest -q
```

## Endpoints principais

- `GET /health`
- `POST /api/companies`
- `GET /api/companies`
- `GET /api/companies/{company_id}`
- `PUT /api/companies/{company_id}`
- `DELETE /api/companies/{company_id}`
- `POST /api/ingestion/run`
- `POST /api/ingestion/run/{company_id}`
- `POST /api/ingestion/extract-batch`
- `GET /api/documents`
- `GET /api/documents/{document_id}`
- `GET /api/metrics`
- `GET /api/metrics/{metric_id}`
- `GET /api/conjuntura?empresa=MRV&ano=2025&trimestre=3`

## Exemplo de chamada

```bash
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

## Exemplo de dado

- Fixture estruturado do boletim de conjuntura 3T2025: `docs/exemplos/conjuntura_3t2025_exemplo.json`.
- Guia de mapeamento desse boletim para `metrics`: `docs/exemplos/README.md`.

## Idempotência

- Cada PDF baixado recebe `SHA-256`.
- Antes da extração, o sistema consulta o catálogo (`documents.file_hash`).
- Hash já existente: cria registro com status `ignored_duplicate` e não chama LLM.
- Hash novo: segue para parsing/chunking/extração.
- Storage dos arquivos pode ser local (`file://`) ou RustFS via S3 (`s3://bucket/key`).

## Contrato semântico

O contrato é definido por `ExtractedMetric` e `ExtractedMetricBatch` (Pydantic), enviado para a OpenAI via Structured Outputs, exigindo:

- resposta aderente ao schema Pydantic;
- `confidence` entre 0 e 1;
- valores ausentes como `null`;
- vínculo com `source_page` e `source_excerpt` quando possível.

Detalhamento da etapa B/C do desafio: `docs/processamento_uda.md`.

## Vocabulário e camada Gold

A extração agora usa um catálogo curado de métricas habitacionais (`app/modules/metrics/catalog.py`) para reduzir variação de nomes como `vendas_contratadas_liquidas` versus `vendas_liquidas`.

Esse catálogo é aplicado em três pontos:

- prompt da LLM, com vocabulário canônico e aliases;
- pós-processamento, normalizando nomes e preenchendo categoria/unidade/moeda quando seguros;
- endpoint `/api/conjuntura`, que atua como camada Gold: mantém `/api/metrics` como visão bruta auditável, mas deduplica a conjuntura por métrica e escolhe a melhor evidência por valor presente, confiança, página e trecho de fonte.

## Linhagem dos dados

Tabela `data_lineage` armazena, para cada métrica:

- `document_id` e `metric_id`;
- `original_url` e `file_hash`;
- `source_page` e `source_excerpt`;
- modelo de extração e versão do prompt;
- timestamp de extração.

## Orquestração com Airflow

- DAG pronta em `dags/uda_pipeline_dag.py`.
- Fluxo: `ingest_new_documents` -> `extract_metrics_batch`.
- A ingestão baixa e salva arquivos no storage (RustFS/local).
- A extração roda em lote para reduzir overhead e custo por documento.

## Limitações conhecidas

- Scraper atual usa heurísticas gerais para links de PDF e pode precisar ajuste por site muito dinâmico.
- Extração OpenAI depende de chave/API ativa.
- Chunking é semântico simples (palavras-chave + blocos por tamanho), sem embeddings vetoriais.
- Parser de tabelas avançadas ainda não está habilitado.

## Próximos passos

- Adicionar suporte a múltiplos provedores LLM (ex.: Anthropic, DeepSeek).
- Melhorar detecção de período com NLP contextual.
- Implementar retries/circuit breaker para ingestão robusta.
- Adicionar endpoint para consultar linhagem explicitamente.
