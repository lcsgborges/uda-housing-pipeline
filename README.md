# Housing Data Intelligence

> Autor: Lucas Guimarães Borges

Pipeline UDA (Unstructured Data Analysis) para coletar documentos não estruturados do mercado habitacional, classificar utilidade documental, extrair métricas e insights com LLM, validar a saída por contrato Pydantic e disponibilizar dados estruturados para análise de conjuntura.

O projeto foi desenhado para transformar PDFs de Relações com Investidores, resultados trimestrais, prévias operacionais e boletins de conjuntura em dados relacionais com rastreabilidade de origem.

## Objetivo

Transformar documentos não estruturados em métricas habitacionais auditáveis:

- coleta automatizada de PDFs;
- idempotência por hash SHA-256;
- parsing de PDF com PyMuPDF;
- classificação pré-extração para ignorar documentos irrelevantes ou marcar PDFs que precisam de OCR;
- seleção de contexto por full scan ou varredura sequencial completa;
- extração estruturada de métricas e insights via Ollama local, OpenAI Responses API ou OpenAI Batch API;
- validação de saída com Pydantic;
- normalização por catálogo canônico de métricas;
- persistência em PostgreSQL;
- storage local ou RustFS S3-compatible;
- linhagem por documento, página, trecho, modelo e versão de prompt;
- API REST para empresas, documentos, métricas e conjuntura.

## Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0 + asyncpg
- Alembic
- Pydantic v2
- PyMuPDF
- OpenAI SDK
- Ollama
- PostgreSQL
- RustFS
- MkDocs Material
- Docker Compose
- pytest + Testcontainers
- Ruff

## Arquitetura

![Pipeline UDA — Fluxo](docs/assets/pipeline.png)

> Figura: Fluxo do pipeline UDA — ingestão, storage (local/RustFS), classificação, extração (PDF parser, segmentação sequencial, LLM), contrato Pydantic, catálogo de métricas, persistência (PostgreSQL) e API FastAPI.

Módulos principais:

| Módulo | Responsabilidade |
| --- | --- |
| `app/core` | Configuração, banco, logging e utilitários. |
| `app/modules/companies` | Cadastro de empresas e fontes RI. |
| `app/modules/ingestion` | Scraping, download, hash, idempotência e scheduler diário. |
| `app/modules/classification` | Classificação de documentos úteis, irrelevantes ou dependentes de OCR. |
| `app/modules/extraction` | Parsing, segmentação, cliente LLM e persistência de métricas e insights. |
| `app/modules/documents` | Catálogo e status de documentos. |
| `app/modules/metrics` | Métricas, catálogo canônico e endpoint de conjuntura. |
| `app/modules/insights` | Consulta de fatos documentais extraídos sem valor numérico obrigatório. |
| `app/modules/lineage` | Linhagem dos dados extraídos. |
| `app/modules/storage` | Storage local ou S3-compatible. |

## Como o Pipeline Funciona

O ciclo começa por chamada manual, scheduler diário ou CLI. A aplicação lê empresas
ativas, descobre PDFs em páginas de RI e centrais MZiQ, baixa documentos novos,
calcula SHA-256 para evitar duplicidade e salva o arquivo em storage local ou
RustFS/S3. O PostgreSQL guarda o estado operacional em `documents`.

Depois, a classificação lê o PDF com PyMuPDF e usa a LLM configurada para decidir
se o documento é útil, irrelevante ou dependente de OCR. Apenas documentos
`classified_useful` seguem para extração. A extração usa full scan em documentos
curtos ou varredura sequencial em documentos longos, valida a resposta com
Pydantic, normaliza nomes pelo catálogo canônico e persiste `metrics`,
`document_insights` e `data_lineage`.

Com `LLM_PROVIDER=openai`, a extração pode ser síncrona pela Responses API ou
assíncrona pela OpenAI Batch API. No Batch API, cada parte documental vira uma
linha JSONL com `custom_id`, o arquivo é enviado com `purpose=batch`, o batch usa
endpoint `/v1/responses` e o import só persiste quando o status está `completed`.

## Documentação

A documentação técnica fica em MkDocs Material.

Rodar localmente:

```bash
uv sync --extra dev
uv run task mkdocs
```

A documentação fica em `http://127.0.0.1:8001`.

Build strict:

```bash
uv run task mkdocs_build
```

O MkDocs não é empacotado no container da aplicação. A imagem Docker leva apenas
o necessário para rodar a API, migrations e pipeline.

Arquivos principais:

- `mkdocs.yml`
- `docs/index.md`
- `docs/projeto/arquitetura.md`
- `docs/projeto/operacao.md`
- `docs/projeto/fluxo-de-dados.md`
- `docs/ambiente/configuracao.md`
- `docs/como_rodar_com_compose.md`

## Configuração

Crie o `.env`:

```bash
cp .env.example .env
```

Variáveis mais importantes:

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` | URL SQLAlchemy async do PostgreSQL. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Credenciais do PostgreSQL no Compose. |
| `LLM_PROVIDER` | `ollama` para execução local ou `openai` para extração remota. |
| `OPENAI_API_KEY` | Chave da OpenAI quando `LLM_PROVIDER=openai`. |
| `OPENAI_MODEL` | Modelo usado pelo cliente OpenAI. |
| `OPENAI_CLASSIFICATION_MODEL` | Modelo usado na classificação com OpenAI. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Endpoint e modelo usados quando `LLM_PROVIDER=ollama`. |
| `OLLAMA_CLASSIFICATION_MODEL` | Modelo usado na classificação com Ollama. |
| `CLASSIFICATION_BATCH_SIZE` | Tamanho padrão dos lotes de classificação. |
| `EXTRACTION_BATCH_SIZE` | Quantos documentos úteis a extração seleciona por rodada; padrão recomendado `1`. |
| `ENABLE_INGESTION_SCHEDULER` | Habilita o ciclo diário junto da API. |
| `INGESTION_SCHEDULE_HOUR`, `INGESTION_SCHEDULE_MINUTE` | Horário diário do ciclo; padrão `02:00`. |
| `SCHEDULER_TIMEZONE` | Timezone do scheduler; padrão `America/Sao_Paulo`. |
| `STORAGE_BACKEND` | `local` ou `rustfs`. |
| `RUSTFS_*` | Configurações do RustFS para execução local. |
| `COMPOSE_RUSTFS_ENDPOINT` | Endpoint interno do RustFS usado pela API no Compose; padrão `rustfs:9000`. |
| `API_PORT`, `POSTGRES_PORT` | Portas publicadas pelo Compose. |

Para extração local sem custo de API externa:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1
```

Use `OLLAMA_BASE_URL=http://localhost:11434` apenas quando a API estiver rodando fora
do Docker. Dentro do Compose, `localhost` aponta para o container da API.

Para extração com OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

Na extração, `EXTRACTION_BATCH_SIZE` controla quantos documentos pendentes são
selecionados do banco por rodada. A LLM recebe payloads menores: documento inteiro
quando couber em `EXTRACTION_FULL_SCAN_MAX_CHARS`, ou partes sequenciais de até
`EXTRACTION_CONTEXT_MAX_CHARS` quando o PDF for longo. Para controlar custo com
OpenAI, mantenha `EXTRACTION_BATCH_SIZE=1`.

Para usar o desconto da OpenAI Batch API, use o fluxo assíncrono:

```bash
curl -X POST "http://localhost:8000/api/ingestion/openai-batch/submit?batch_size=1"
curl "http://localhost:8000/api/ingestion/openai-batch/{batch_id}"
curl -X POST "http://localhost:8000/api/ingestion/openai-batch/{batch_id}/import"
```

O `submit` cria um arquivo JSONL com uma request `/v1/responses` por parte de documento,
faz upload com `purpose=batch` e cria o batch com janela `24h`. O `batch_size` controla
quantos documentos entram na submissão; documentos longos podem gerar várias requests.
O `import` deve ser usado somente quando o status estiver `completed`.

## Docker Compose

Há um único `compose.yml`. O comportamento de desenvolvimento ou produção é definido pelo `.env`.
O Compose sobe API, PostgreSQL e RustFS; a documentação roda localmente por task.

```bash
docker compose --env-file .env up --build
```

Atalhos:

```bash
uv run task compose_up
uv run task compose_down
```

Serviços:

| Serviço | URL |
| --- | --- |
| API | `http://localhost:8000` |
| Swagger/OpenAPI | `http://localhost:8000/docs` |
| PostgreSQL | `localhost:5432` |
| RustFS S3 API | `http://localhost:9000` |
| RustFS Console | `http://localhost:9001` |

Para rodar em segundo plano:

```bash
docker compose --env-file .env up --build -d
```

## Dockerfile

O projeto usa um único `Dockerfile` otimizado para a API:

- estágio `builder`: instala dependências de runtime com `uv sync --frozen --no-dev`;
- estágio `api`: copia somente `.venv`, `app`, `alembic`, `docker` e `alembic.ini`;
- executa como usuário não-root;
- não copia `docs`, `mkdocs.yml`, testes, coverage ou artefatos locais.

Build manual:

```bash
docker build -t hdi-api:latest .
```

## Execução Local Sem Docker

Instale dependências:

```bash
uv sync --extra dev
```

Rode migrations:

```bash
uv run alembic upgrade head
```

Suba a API:

```bash
uv run uvicorn app.main:app --reload
```

Com scheduler diário às 02:00:

```bash
ENABLE_INGESTION_SCHEDULER=true uv run uvicorn app.main:app --reload
```

Executar o ciclo diário sob demanda via CLI:

```bash
uv run python -m app.modules.ingestion.scheduler
```

## Endpoints Principais

| Endpoint | Uso |
| --- | --- |
| `GET /health` | Saúde da API. |
| `POST /api/companies` | Cadastrar empresa. |
| `GET /api/companies` | Listar empresas. |
| `POST /api/ingestion/run` | Rodar ciclo geral: ingestão, classificação e extração em lote. |
| `POST /api/ingestion/run/{company_id}` | Rodar ciclo por empresa. |
| `POST /api/ingestion/classify-batch` | Classificar um lote de documentos baixados. |
| `POST /api/ingestion/extract-batch` | Extrair um lote de documentos pendentes. |
| `POST /api/ingestion/openai-batch/submit` | Submeter extração offline na OpenAI Batch API. |
| `GET /api/ingestion/openai-batch/{batch_id}` | Consultar status do batch OpenAI. |
| `POST /api/ingestion/openai-batch/{batch_id}/import` | Baixar e persistir resultado do batch OpenAI. |
| `GET /api/documents` | Listar documentos. |
| `GET /api/metrics` | Listar métricas brutas. |
| `GET /api/insights` | Listar insights documentais extraídos. |
| `GET /api/conjuntura` | Consultar camada Gold de conjuntura. |

Exemplo:

```bash
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

## Métricas, Catálogo e Camada Gold

O catálogo em `app/modules/metrics/catalog.py` padroniza nomes e aliases de métricas habitacionais.

Exemplo:

| Alias | Nome canônico |
| --- | --- |
| `vendas contratadas líquidas` | `vendas_liquidas` |
| `valor geral de vendas lançado` | `vgv_lancado` |
| `dívida líquida` | `divida_liquida` |

A API mantém duas visões:

- `/api/metrics`: visão bruta e auditável;
- `/api/conjuntura`: camada Gold, deduplicada por métrica canônica e ordenada por qualidade de evidência.

## Linhagem

Cada métrica persistida gera registro em `data_lineage` com:

- `document_id`;
- `metric_id`;
- `original_url`;
- `file_hash`;
- `source_page`;
- `source_excerpt`;
- `extraction_model`;
- `extraction_prompt_version`;
- `extracted_at`.

## Testes e Lint

Rodar lint:

```bash
uv run task lint
```

Rodar testes:

```bash
uv run task test
```

Os testes usam Testcontainers para subir PostgreSQL efêmero. Docker precisa estar disponível.

## CI/CD

O workflow em `.github/workflows/ci.yml` roda:

- Ruff;
- pytest;
- `task mkdocs_build`;
- deploy do MkDocs no GitHub Pages em push para `main`.

Para o deploy funcionar, configure no GitHub:

```text
Settings -> Pages -> Build and deployment -> Source: GitHub Actions
```

## GitHub Pages

O MkDocs é publicado automaticamente pelo GitHub Actions quando há push para `main`.

Em pull requests, o workflow apenas valida lint, testes e build da documentação.

## Limitações Conhecidas

- Scraper usa heurísticas gerais para links de PDF.
- OpenAI depende de chave ativa; Ollama depende do servidor local e do modelo baixado.
- Chunking ainda é semântico simples, sem embeddings vetoriais.
- Parser de tabelas avançadas ainda não está habilitado.

## Próximos Passos

- Adicionar endpoint dedicado de linhagem.
- Melhorar detecção contextual de período.
- Implementar retries/circuit breaker na ingestão.
- Expandir catálogo de métricas.
- Adicionar recuperação semântica com embeddings para documentos longos.
