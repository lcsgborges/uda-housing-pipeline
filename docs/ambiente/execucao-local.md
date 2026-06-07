# Executar Localmente

## API

Com dependências instaladas e `.env` configurado:

```bash
uv run uvicorn app.main:app --reload
```

Acesse:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Migrations

Antes de usar a API com banco limpo:

```bash
uv run alembic upgrade head
```

## Fluxo Manual

1. Cadastre uma empresa.
2. Execute `POST /api/ingestion/run` para rodar o ciclo completo.
3. Se quiser controlar as etapas separadamente, use `classify-batch` e `extract-batch`.
4. Com `LLM_PROVIDER=openai`, use os endpoints `openai-batch` para extração assíncrona.
5. Consulte documentos, métricas, insights ou conjuntura.

## Exemplos de Chamadas

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/api/ingestion/run
```

```bash
curl -X POST "http://localhost:8000/api/ingestion/classify-batch?batch_size=5"
```

```bash
curl -X POST "http://localhost:8000/api/ingestion/extract-batch?batch_size=1"
```

Para o fluxo com desconto da OpenAI Batch API:

```bash
curl -X POST "http://localhost:8000/api/ingestion/openai-batch/submit?batch_size=1"
curl "http://localhost:8000/api/ingestion/openai-batch/{batch_id}"
curl -X POST "http://localhost:8000/api/ingestion/openai-batch/{batch_id}/import"
```

Use o `import` apenas quando a consulta de status retornar `completed`.

```bash
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

## Scheduler

Para executar ingestão e extração diária junto da API:

```bash
ENABLE_INGESTION_SCHEDULER=true uv run uvicorn app.main:app --reload
```

## CLI de Ingestão

```bash
uv run python -m app.modules.ingestion.scheduler
```

## Documentação Local

```bash
uv run task mkdocs
```

Acesse `http://127.0.0.1:8001`.
