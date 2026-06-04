# Padrão de Projeto

## Organização de Módulos

Cada módulo de domínio segue uma estrutura previsível:

```text
app/modules/<modulo>/
├── models.py       # SQLAlchemy
├── schemas.py      # Pydantic
├── repository.py   # Consultas e persistência
├── service.py      # Regra de negócio
└── router.py       # Endpoints FastAPI
```

Nem todo módulo precisa de todos os arquivos. `storage` e `extraction`, por exemplo, têm responsabilidades mais técnicas e não expõem sempre CRUD completo.

## Regras de Implementação

- Routers não devem conter regra de negócio complexa.
- Services coordenam fluxo e validações de domínio.
- Repositories isolam consultas SQLAlchemy.
- Schemas Pydantic representam contrato de API ou contrato semântico.
- Models SQLAlchemy representam persistência, não regras de domínio.
- Utilitários compartilhados ficam em `app/core`.

## Tratamento de Estado

Documentos usam `DocumentStatus`:

| Status | Significado |
| --- | --- |
| `discovered` | Documento descoberto, ainda não baixado. |
| `downloaded` | PDF salvo e pronto para extração. |
| `processing` | Em processamento. |
| `processed` | Métricas extraídas e persistidas. |
| `failed` | Falha no pipeline. |
| `ignored_duplicate` | Hash já processado anteriormente. |

## Contratos

O contrato mais importante é a saída da extração:

- `ExtractedMetric`
- `ExtractedMetricBatch`
- `ExtractedDocumentMetrics`
- `ExtractedBatchResponse`

Esses schemas garantem que o payload da LLM seja validado antes de persistir.

## Normalização

Não confie que o modelo sempre retornará o mesmo nome para uma métrica. Use `app/modules/metrics/catalog.py` para aliases, nome canônico, categoria e unidade esperada.

## Testes

Ao adicionar comportamento:

- teste o contrato se mudou schema Pydantic;
- teste serviço se mudou regra de negócio;
- teste API se mudou resposta HTTP;
- teste repositório quando a consulta tiver filtros, joins ou ordenação relevantes.

## Migrações

Mudanças em models persistidos exigem migration Alembic.

```bash
uv run alembic revision --autogenerate -m "descricao"
uv run alembic upgrade head
```

Revise a migration gerada antes de aplicar.
