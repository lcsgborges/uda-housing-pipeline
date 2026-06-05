# Testes

## Ferramentas

- `pytest`
- `pytest-asyncio`
- `Testcontainers`
- PostgreSQL efêmero em Docker
- `ruff`

## Rodar Tudo

```bash
uv run task test
```

Os testes sobem um PostgreSQL em container. Docker precisa estar ativo.

## Lint

```bash
uv run task lint
```

## Cobertura

```bash
uv run pytest --cov=app
```

## Organização

| Diretório | Cobertura |
| --- | --- |
| `tests/api` | Endpoints FastAPI. |
| `tests/classification` | Classificação de documentos e transições de status. |
| `tests/companies` | Repositório e serviço de empresas. |
| `tests/documents` | Serviço de documentos e leitura de arquivo. |
| `tests/ingestion` | Scraper, download, hashing e idempotência. |
| `tests/extraction` | Parser, chunking, LLM client, contrato e serviço. |
| `tests/metrics` | Catálogo, repositório, serviço e camada de conjuntura. |
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
- contrato de classificação;
- ranking da camada de conjuntura;
- catálogo de métricas;
- estados de documento;
- regra de idempotência;
- persistência ou migrations.
