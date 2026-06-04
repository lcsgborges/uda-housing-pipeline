# Testes

## Ferramentas

- `pytest`
- `pytest-asyncio`
- `Testcontainers`
- PostgreSQL efêmero em Docker
- `ruff`

## Rodar Tudo

```bash
uv run --extra dev pytest -q
```

Os testes sobem um PostgreSQL em container. Docker precisa estar ativo.

## Lint

```bash
uv run --extra dev ruff check app tests
```

## Cobertura

```bash
uv run --extra dev pytest --cov=app
```

Ou use a task:

```bash
uv run task test
```

## Organização

| Diretório | Cobertura |
| --- | --- |
| `tests/api` | Endpoints FastAPI. |
| `tests/ingestion` | Scraper, download, hashing e idempotência. |
| `tests/extraction` | Parser, chunking, LLM client, contrato e serviço. |
| `tests/metrics` | Catálogo de métricas. |
| `tests/lineage` | Repositório e schema de linhagem. |
| `tests/storage` | Storage local e S3 compatível. |
| `tests/fixtures` | Exemplos estruturados. |

## Configuração de Teste

`tests/conftest.py` força:

- `APP_ENV=test`
- `DATABASE_URL` do container PostgreSQL
- `STORAGE_BACKEND=local`
- `DOCUMENTS_DIR=/tmp/uda-test-documents`

Isso evita depender de RustFS para testes automatizados.

## Quando Adicionar Testes

Adicione ou atualize testes quando alterar:

- contrato Pydantic;
- ranking da camada de conjuntura;
- catálogo de métricas;
- estados de documento;
- regra de idempotência;
- persistência ou migrations.
