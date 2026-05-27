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
- `app/tests`: testes unitários e de API.

## Tecnologias

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL (produção) / SQLite (local)
- Pydantic v2 + pydantic-settings
- PyMuPDF
- httpx + BeautifulSoup4
- OpenAI SDK (provedor configurável)
- pytest
- Ruff

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Configuração `.env`

```bash
cp .env.example .env
```

Variáveis principais:

- `DATABASE_URL=sqlite:///./pipeline_uda.db` (local)
- `LLM_PROVIDER=fake` para modo de desenvolvimento sem chave
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY` para extração real
- `OPENAI_MODEL=gpt-4.1-mini`
- `DOCUMENTS_DIR=./data/documents`

## Executar servidor

```bash
uvicorn app.main:app --reload
```

## Rodar migrations

```bash
alembic upgrade head
```

## Rodar ingestão

- Via CLI:

```bash
python -m app.modules.ingestion.scheduler
```

- Via API:

```http
POST /api/ingestion/run
POST /api/ingestion/run/{company_id}
```

## Rodar testes

```bash
pytest -q
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
- `GET /api/documents`
- `GET /api/documents/{document_id}`
- `GET /api/metrics`
- `GET /api/metrics/{metric_id}`
- `GET /api/conjuntura?empresa=MRV&ano=2025&trimestre=3`

## Exemplo de chamada

```bash
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

## Idempotência

- Cada PDF baixado recebe `SHA-256`.
- Antes da extração, o sistema consulta o catálogo (`documents.file_hash`).
- Hash já existente: cria registro com status `ignored_duplicate` e não chama LLM.
- Hash novo: segue para parsing/chunking/extração.

## Contrato semântico

O contrato é definido por `ExtractedMetric` e `ExtractedMetricBatch` (Pydantic), exigindo:

- JSON válido;
- `confidence` entre 0 e 1;
- valores ausentes como `null`;
- vínculo com `source_page` e `source_excerpt` quando possível.

## Linhagem dos dados

Tabela `data_lineage` armazena, para cada métrica:

- `document_id` e `metric_id`;
- `original_url` e `file_hash`;
- `source_page` e `source_excerpt`;
- modelo de extração e versão do prompt;
- timestamp de extração.

## Limitações conhecidas

- Scraper atual usa heurísticas gerais para links de PDF e pode precisar ajuste por site muito dinâmico.
- Extração OpenAI depende de chave/API ativa.
- Chunking é semântico simples (palavras-chave + blocos por tamanho), sem embeddings.
- Parser de tabelas avançadas ainda não está habilitado.

## Próximos passos

- Incluir scheduler com APScheduler para execução diária automática.
- Adicionar suporte a múltiplos provedores LLM (ex.: Anthropic, DeepSeek).
- Melhorar detecção de período com NLP contextual.
- Implementar retries/circuit breaker para ingestão robusta.
- Adicionar endpoint para consultar linhagem explicitamente.
