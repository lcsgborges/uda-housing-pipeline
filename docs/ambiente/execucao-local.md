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
2. Execute ingestão.
3. Execute classificação em lote, se a ingestão foi separada.
4. Execute extração em lote para documentos classificados como úteis.
5. Consulte métricas, insights ou conjuntura.

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
curl -X POST "http://localhost:8000/api/ingestion/extract-batch?batch_size=5"
```

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
