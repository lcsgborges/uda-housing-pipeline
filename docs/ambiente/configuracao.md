# Configuração do Ambiente

## Pré-requisitos

- Python 3.12 ou superior.
- `uv`.
- Docker, para PostgreSQL local, RustFS e testes com Testcontainers.
- Chave OpenAI, se for usar extração real.

## Instalação

```bash
uv sync --extra dev
```

## `.env`

Crie o arquivo local:

```bash
cp .env.example .env
```

Variáveis principais:

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` | URL SQLAlchemy async do PostgreSQL. |
| `API_PORT` | Porta publicada da API nos composes. |
| `DOCS_PORT` | Porta publicada da documentação MkDocs. |
| `POSTGRES_PORT` | Porta publicada do PostgreSQL. |
| `RUSTFS_API_PORT` | Porta publicada da API S3 do RustFS. |
| `RUSTFS_CONSOLE_PORT` | Porta publicada do console RustFS. |
| `LLM_PROVIDER` | `fake` ou `openai`. |
| `OPENAI_API_KEY` | Chave para extração real. |
| `OPENAI_MODEL` | Modelo usado pelo cliente OpenAI. |
| `STORAGE_BACKEND` | `local` ou `rustfs`. |
| `DOCUMENTS_DIR` | Diretório para storage local. |
| `RUSTFS_*` | Configuração do storage S3 compatível. |
| `EXTRACTION_BATCH_SIZE` | Tamanho padrão de lote. |
| `ENABLE_INGESTION_SCHEDULER` | Habilita scheduler junto da API. |
| `INGESTION_POLL_INTERVAL_MINUTES` | Intervalo do scheduler. |

## Modos de LLM

### Desenvolvimento Sem Custo

```env
LLM_PROVIDER=fake
```

### Extração Real

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

## Banco

Com PostgreSQL disponível:

```bash
uv run alembic upgrade head
```

Para criar migrations:

```bash
uv run alembic revision --autogenerate -m "descricao"
```

## MkDocs

Para servir esta documentação:

```bash
uv run --extra dev mkdocs serve
```
