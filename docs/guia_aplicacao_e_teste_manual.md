# Guia da Aplicação e Teste Manual

## 1) Visão geral

A aplicação implementa um pipeline UDA (Unstructured Data Analysis) para o setor habitacional:

1. observa fontes de RI das empresas;
2. detecta novos PDFs (prévias/relatórios);
3. aplica idempotência por hash para evitar duplicidade;
4. extrai métricas com LLM usando contrato semântico estruturado (em lote quando necessário);
5. registra linhagem (origem do dado);
6. disponibiliza os dados via API REST.

A stack principal:

- API: `FastAPI`
- Banco: `SQLAlchemy` assíncrono com `AsyncSession`
- Banco: `PostgreSQL` via `asyncpg`
- Scheduler: `APScheduler`
- Orquestração DAG: `Airflow`
- Object storage: `RustFS` (S3-compatible) ou filesystem local
- Parsing PDF: `PyMuPDF`
- LLM: cliente fake (dev) ou OpenAI
- Ambiente/dependências: `uv`
- Testes: `pytest` com `Testcontainers` para PostgreSQL efêmero

## 2) Arquitetura por módulos

- `app/modules/companies`: cadastro de empresas e URL de RI.
- `app/modules/ingestion`: scraping de links PDF, download, hash, deduplicação e orquestração de ingestão.
- `app/modules/extraction`: parsing do PDF, estratégia full-scan/chunking e extração via LLM.
- `app/modules/documents`: catálogo de documentos processados.
- `app/modules/metrics`: métricas extraídas e endpoint de conjuntura.
- `app/modules/lineage`: rastreabilidade origem -> métrica.
- `app/core`: config, banco e logging.

## 3) Fluxo ponta a ponta

### 3.1 Cadastro da empresa

Você cadastra a empresa com nome, ticker e URL de RI em `POST /api/companies`.

### 3.2 Ingestão

Ao chamar `POST /api/ingestion/run`:

1. o scraper busca links de PDFs na URL de RI;
2. cada PDF é baixado e recebe `SHA-256`;
3. o hash é consultado no catálogo de documentos;
4. se o hash já existe: status `ignored_duplicate`;
5. se o hash é novo: documento segue para extração.

### 3.3 Extração semântica

Para documentos novos:

1. PDF é convertido para texto por página;
2. estratégia adaptativa de contexto:
   - documento curto: `full_scan`;
   - documento longo: `chunking` com limite de contexto;
3. LLM extrai métricas em JSON estruturado;
4. payload é validado por contrato semântico (tipos, campos, confiança, `null` para ausentes);
5. métricas são gravadas no banco.

### 3.4 Linhagem

Para cada métrica, o sistema salva:

- `document_id`, `file_hash`, `original_url`
- `source_page`, `source_excerpt`
- `extraction_model`, `extraction_prompt_version`
- timestamp de extração

### 3.5 Consulta

A API permite:

- listar/consultar métricas (`/api/metrics`)
- consultar conjuntura por empresa/ano/trimestre (`/api/conjuntura`)

## 4) Configuração de ambiente

1. instalar dependências:

```bash
uv sync --extra dev
```

2. configurar variáveis:

```bash
cp .env.example .env
```

3. principais variáveis no `.env`:

- `DATABASE_URL=postgresql+asyncpg://uda:uda@localhost:5432/uda`
- `POSTGRES_DB=uda`
- `POSTGRES_USER=uda`
- `POSTGRES_PASSWORD=uda`
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY` (extração real)
- `LLM_PROVIDER=fake` (dev, sem custo de API)
- `OPENAI_MODEL=gpt-4.1-mini`
- `ENABLE_INGESTION_SCHEDULER=false` (manual) ou `true` (contínuo)
- `INGESTION_POLL_INTERVAL_MINUTES=1440` (periodicidade do scheduler)
- `STORAGE_BACKEND=local` ou `rustfs`
- `RUSTFS_ENDPOINT`, `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, `RUSTFS_BUCKET`
- `EXTRACTION_BATCH_SIZE=5`

## 5) Como subir com Docker Compose

1. Copiar configuração:

```bash
cp .env.example .env
```

2. Preencher `OPENAI_API_KEY` no `.env`.

3. Subir API + RustFS:

```bash
docker compose --env-file .env up --build
```

4. Validar:

```bash
curl "http://127.0.0.1:8000/health"
```

Endpoints úteis:

- API: `http://127.0.0.1:8000`
- Docs: `http://127.0.0.1:8000/docs`
- RustFS S3 API: `http://127.0.0.1:9000`
- RustFS Console: `http://127.0.0.1:9001`

## 6) Como subir a aplicação sem Docker

1. aplicar migrations:

```bash
uv run alembic upgrade head
```

2. iniciar API:

```bash
uv run uvicorn app.main:app --reload
```

3. healthcheck:

```bash
curl "http://127.0.0.1:8000/health"
```

Esperado:

```json
{"status":"ok"}
```

## 7) Teste manual completo (roteiro)

### Passo 1 - Cadastrar empresa

```bash
curl -X POST "http://127.0.0.1:8000/api/companies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MRV",
    "ticker": "MRVE3",
    "ri_url": "https://ri.mrv.com.br",
    "is_active": true
  }'
```

Validar:

- resposta `201`
- objeto com `id`, `name`, `ticker`, `ri_url`

### Passo 2 - Executar ingestão manual

```bash
curl -X POST "http://127.0.0.1:8000/api/ingestion/run"
```

Validar campos de retorno:

- `companies`
- `discovered`
- `processed`
- `ignored_duplicates`

### Passo 3 - Consultar documentos

```bash
curl "http://127.0.0.1:8000/api/documents"
```

Validar:

- documentos com status (`downloaded`, `processed`, `ignored_duplicate`, `failed`)
- `file_hash`, `original_url`, `year`, `quarter`

### Passo 4 - Consultar métricas extraídas

```bash
curl "http://127.0.0.1:8000/api/metrics"
```

Validar:

- `metric_name`, `value`, `confidence`
- `period_year`, `period_quarter`
- `source_page` e `source_excerpt` quando disponível

### Passo 5 - Consultar endpoint de conjuntura

```bash
curl "http://127.0.0.1:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

Validar:

- retorno da empresa/perfil temporal correto
- lista de métricas com fonte e confiança

### Passo 6 - Validar idempotência

Execute a ingestão novamente:

```bash
curl -X POST "http://127.0.0.1:8000/api/ingestion/run"
```

Validar:

- aumento de `ignored_duplicates`
- ausência de reprocessamento desnecessário para o mesmo hash

## 8) Modo contínuo (scheduler)

Para observação contínua de novas publicações:

```bash
ENABLE_INGESTION_SCHEDULER=true uv run uvicorn app.main:app --reload
```

Com isso, o job de ingestão roda automaticamente no intervalo definido por:

- `INGESTION_POLL_INTERVAL_MINUTES`

## 9) DAG do Airflow (ingestão + extração batch)

A DAG já está pronta em:

- `dags/uda_pipeline_dag.py`

Pipeline da DAG:

1. `ingest_new_documents`: descobre e baixa novos documentos sem extrair imediatamente;
2. `extract_metrics_batch`: pega documentos `downloaded` e envia em lote para LLM.

## 10) Testes automatizados

Rodar suite:

```bash
uv run --extra dev pytest -q
```

Os testes usam Testcontainers e precisam de Docker disponível para subir um PostgreSQL efêmero.

## 11) Problemas comuns

- `No module named asyncpg` ou `No module named testcontainers`:
  - rode `uv sync --extra dev`.

- falha ao subir PostgreSQL nos testes:
  - valide se o Docker está em execução e se a imagem `postgres:16-alpine` pode ser baixada.

- erro de conexão com RustFS:
  - valide `STORAGE_BACKEND=rustfs`, endpoint e credenciais.

- `conflito de cadastro de empresa`:
  - nome/ticker duplicado retorna `409`.

- `nenhum PDF encontrado`:
  - revisar URL de RI, estrutura do site e conectividade.

- `métricas vazias`:
  - em `LLM_PROVIDER=fake`, os dados são simulados; para extração real configure OpenAI.
