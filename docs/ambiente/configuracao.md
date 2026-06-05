# Configuração do Ambiente

## Pré-requisitos

- Python 3.12 ou superior.
- `uv`.
- Docker, para PostgreSQL local, RustFS e testes com Testcontainers.
- Chave OpenAI, se for usar extração remota.
- Ollama local, se for usar `LLM_PROVIDER=ollama`.

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
| `API_PORT` | Porta publicada da API no Compose. |
| `POSTGRES_PORT` | Porta publicada do PostgreSQL. |
| `RUSTFS_API_PORT` | Porta publicada da API S3 do RustFS. |
| `RUSTFS_CONSOLE_PORT` | Porta publicada do console RustFS. |
| `LLM_PROVIDER` | `ollama` ou `openai`. |
| `OPENAI_API_KEY` | Chave para extração remota com OpenAI. |
| `OPENAI_MODEL` | Modelo usado pelo cliente OpenAI. |
| `OPENAI_CLASSIFICATION_MODEL` | Modelo usado para classificação quando `LLM_PROVIDER=openai`. |
| `OLLAMA_BASE_URL` | URL do servidor Ollama. |
| `OLLAMA_MODEL` | Modelo local usado pelo Ollama. |
| `OLLAMA_CLASSIFICATION_MODEL` | Modelo usado para classificação quando `LLM_PROVIDER=ollama`. |
| `STORAGE_BACKEND` | `local` ou `rustfs`. |
| `DOCUMENTS_DIR` | Diretório para storage local. |
| `RUSTFS_*` | Configuração do storage S3 compatível. |
| `COMPOSE_RUSTFS_ENDPOINT` | Endpoint interno do RustFS para a API dentro do Docker Compose. |
| `CLASSIFICATION_BATCH_SIZE` | Tamanho padrão dos lotes de classificação. |
| `EXTRACTION_BATCH_SIZE` | Tamanho padrão de lote. |
| `CLASSIFICATION_CONTEXT_MAX_CHARS` | Tamanho máximo da amostra enviada ao classificador. |
| `CLASSIFICATION_SAMPLE_PAGES` | Quantidade de páginas iniciais usadas na amostra de classificação. |
| `EXTRACTION_FULL_SCAN_MAX_CHARS` | Limite para enviar documento inteiro em extração. |
| `EXTRACTION_CONTEXT_MAX_CHARS` | Limite de contexto para chunks semânticos. |
| `ENABLE_INGESTION_SCHEDULER` | Habilita scheduler junto da API. |
| `INGESTION_SCHEDULE_HOUR` | Hora diária do ciclo; padrão `2`. |
| `INGESTION_SCHEDULE_MINUTE` | Minuto diário do ciclo; padrão `0`. |
| `SCHEDULER_TIMEZONE` | Timezone do scheduler; padrão `America/Sao_Paulo`. |

## Modos de LLM

### Ollama Local

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

Quando a API roda via Docker Compose e o Ollama roda na máquina host, use:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Dentro do container, `localhost` é o próprio container da API, não a máquina host.
Em Linux, se o Ollama estiver ouvindo apenas em `127.0.0.1`, suba o servidor com
`OLLAMA_HOST=0.0.0.0:11434 ollama serve`.

## RustFS no Docker Compose

Para execução local fora do Docker, `RUSTFS_ENDPOINT=localhost:9000` aponta para a
porta publicada na máquina. Dentro do Docker Compose, o container da API precisa
falar com o serviço `rustfs` pela rede interna; por isso o Compose usa
`COMPOSE_RUSTFS_ENDPOINT=rustfs:9000` e injeta esse valor como `RUSTFS_ENDPOINT`
no container.

### OpenAI em Lote

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_CLASSIFICATION_MODEL=gpt-4.1-mini
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
uv run task mkdocs
```

Acesse `http://127.0.0.1:8001`.

Para validar antes de publicar:

```bash
uv run task mkdocs_build
```
