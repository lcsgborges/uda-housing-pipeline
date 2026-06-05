# Como Rodar com Docker Compose

Este projeto possui stacks separadas para desenvolvimento e produção. As duas sobem API FastAPI, PostgreSQL, RustFS e documentação MkDocs Material.

## Serviços Expostos

| Serviço | Desenvolvimento | Produção | Uso |
| --- | --- | --- | --- |
| API | `http://localhost:8000` | `http://localhost:8000` | Backend FastAPI. |
| Swagger/OpenAPI | `http://localhost:8000/docs` | `http://localhost:8000/docs` | Teste manual da API. |
| MkDocs | `http://localhost:8001` | `http://localhost:8001` | Documentação técnica. |
| PostgreSQL | `localhost:5432` | `localhost:5432` | Banco relacional. |
| RustFS S3 API | `http://localhost:9000` | `http://localhost:9000` | Object storage. |
| RustFS Console | `http://localhost:9001` | `http://localhost:9001` | Console web do storage. |

## 1. Configurar ambiente

```bash
cp .env.example .env
```

Para usar Ollama local, mantenha ou ajuste:

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1
```

> Em execução fora do Docker, use `OLLAMA_BASE_URL=http://localhost:11434`.
> Dentro do Compose, `localhost` aponta para o container da API; para acessar o Ollama
> instalado na máquina host, use `host.docker.internal`.
> Se ainda houver `Connection refused` no Linux, inicie o Ollama no host com
> `OLLAMA_HOST=0.0.0.0:11434 ollama serve`.

Para usar OpenAI, preencha:

```bash
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
```

Portas podem ser alteradas no `.env`:

```env
API_PORT=8000
DOCS_PORT=8001
POSTGRES_PORT=5432
RUSTFS_API_PORT=9000
RUSTFS_CONSOLE_PORT=9001
```

## 2. Subir Desenvolvimento

```bash
docker compose --env-file .env -f compose.dev.yml up --build
```

Atalhos com taskipy:

```bash
uv run task compose_up
uv run task compose_down
```

No desenvolvimento:

- `api` usa `Dockerfile.dev` e roda `uvicorn --reload`;
- `docs` usa `mkdocs serve` com reload;
- código e documentação são montados por bind mount.

## 3. Subir Produção

```bash
docker compose --env-file .env -f compose.prod.yml up --build -d
```

Atalhos:

```bash
uv run task compose_prod_up
uv run task compose_prod_down
```

Na produção:

- `api` usa o target `api` do `Dockerfile.prod`;
- `docs` usa o target `docs` do `Dockerfile.prod`;
- a documentação é gerada com `mkdocs build --strict` e servida por Nginx;
- não há bind mount de código.

Credenciais locais do PostgreSQL:

```bash
POSTGRES_DB=uda
POSTGRES_USER=uda
POSTGRES_PASSWORD=uda
DATABASE_URL=postgresql+asyncpg://uda:uda@localhost:5432/uda
```

Credenciais locais do RustFS:

```bash
RUSTFS_ACCESS_KEY=rustfsadmin
RUSTFS_SECRET_KEY=rustfsadmin
```

## 4. Validar saúde

```bash
curl "http://localhost:8000/health"
```

Resposta esperada:

```json
{"status":"ok"}
```

Abra também:

```text
http://localhost:8001
http://localhost:9001
```

## 5. Cadastrar uma empresa

```bash
curl -X POST "http://localhost:8000/api/companies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MRV",
    "ticker": "MRVE3",
    "ri_url": "https://ri.mrv.com.br",
    "is_active": true
  }'
```

## 6. Rodar ingestão e extração

```bash
curl -X POST "http://localhost:8000/api/ingestion/run"
```

O fluxo baixa PDFs novos, calcula SHA-256, ignora duplicados, grava o arquivo no RustFS e extrai métricas estruturadas com o provider configurado. Com OpenAI, os documentos pendentes são agrupados por lote; com Ollama, são processados sequencialmente no servidor local.

## 7. Consultar resultados

```bash
curl "http://localhost:8000/api/documents"
curl "http://localhost:8000/api/metrics"
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

## 8. Scheduler diário

No `.env`, habilite:

```bash
ENABLE_INGESTION_SCHEDULER=true
INGESTION_SCHEDULE_HOUR=2
INGESTION_SCHEDULE_MINUTE=0
SCHEDULER_TIMEZONE=America/Sao_Paulo
```

Depois reinicie:

```bash
docker compose --env-file .env -f compose.dev.yml up --build
```

## 9. Parar e limpar

Parar containers:

```bash
docker compose --env-file .env -f compose.dev.yml down
```

Parar e remover volumes persistidos:

```bash
docker compose --env-file .env -f compose.dev.yml down -v
```
