# Como Rodar com Docker Compose

Este projeto usa um único `Dockerfile` e um único `compose.yml`. A imagem é otimizada para rodar a API FastAPI e não inclui MkDocs, documentação, testes ou artefatos locais. Desenvolvimento e produção são controlados pelo `.env`.

## Serviços Expostos

| Serviço | URL padrão | Uso |
| --- | --- | --- |
| API | `http://localhost:8000` | Backend FastAPI. |
| Swagger/OpenAPI | `http://localhost:8000/docs` | Teste manual da API. |
| PostgreSQL | `localhost:5432` | Banco relacional. |
| RustFS S3 API | `http://localhost:9000` | Object storage. |
| RustFS Console | `http://localhost:9001` | Console web do storage. |

Para abrir a documentação técnica, rode MkDocs localmente:

```bash
uv run task mkdocs
```

Acesse `http://127.0.0.1:8001`.

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
POSTGRES_PORT=5432
RUSTFS_API_PORT=9000
RUSTFS_CONSOLE_PORT=9001
```

Para RustFS, mantenha:

```env
RUSTFS_ENDPOINT=localhost:9000
COMPOSE_RUSTFS_ENDPOINT=rustfs:9000
```

`RUSTFS_ENDPOINT` atende execuções fora do Docker. `COMPOSE_RUSTFS_ENDPOINT` é o
nome do serviço usado pela API dentro do Compose. Usar `localhost:9000` dentro do
container faz a API tentar conectar nela mesma e causa `Connection refused`.

## 2. Subir a stack

```bash
docker compose --env-file .env up --build
```

Atalhos com taskipy:

```bash
uv run task compose_up
uv run task compose_down
```

Para rodar em segundo plano, use:

```bash
docker compose --env-file .env up --build -d
```

O `Dockerfile` usa multi-stage build:

- instala apenas dependências de runtime;
- copia apenas código da API, Alembic e entrypoint;
- executa como usuário não-root;
- deixa documentação e MkDocs fora da imagem.

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

## 3. Validar saúde

```bash
curl "http://localhost:8000/health"
```

Resposta esperada:

```json
{"status":"ok"}
```

Abra também:

```text
http://localhost:9001
```

## 4. Cadastrar uma empresa

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

## 5. Rodar ingestão e extração

```bash
curl -X POST "http://localhost:8000/api/ingestion/run"
```

O fluxo baixa PDFs novos, calcula SHA-256, ignora duplicados, grava o arquivo no
RustFS, classifica documentos baixados e extrai métricas/insights estruturados
dos documentos úteis com o provider configurado.

Com Ollama, o lote é processado sequencialmente no servidor local. Com OpenAI, a
extração pode ser síncrona (`extract-batch`) ou assíncrona pela Batch API
(`openai-batch/submit`, status e import). Para grandes documentos, um único PDF
pode gerar várias partes e várias requests de LLM.

## 6. Consultar resultados

```bash
curl "http://localhost:8000/api/documents"
curl "http://localhost:8000/api/metrics"
curl "http://localhost:8000/api/insights"
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

## 7. Scheduler diário

No `.env`, habilite:

```bash
ENABLE_INGESTION_SCHEDULER=true
INGESTION_SCHEDULE_HOUR=2
INGESTION_SCHEDULE_MINUTE=0
SCHEDULER_TIMEZONE=America/Sao_Paulo
```

Depois reinicie:

```bash
docker compose --env-file .env up --build
```

## 8. Parar e limpar

Parar containers:

```bash
docker compose --env-file .env down
```

Parar e remover volumes persistidos:

```bash
docker compose --env-file .env down -v
```
