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

Nem todo módulo precisa de todos os arquivos. `storage` e `extraction`, por exemplo, têm responsabilidades mais técnicas e não expõem sempre CRUD completo. `classification` concentra o filtro semântico pré-extração e `insights` expõe consulta de fatos documentais extraídos junto das métricas.

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
| `downloaded` | PDF salvo e pronto para classificação. |
| `classifying` | Documento em classificação de utilidade. |
| `classified_useful` | Documento útil e pronto para extração. |
| `processing` | Documento em extração de métricas e insights. |
| `processed` | Métricas extraídas e persistidas. |
| `failed` | Falha no pipeline. |
| `ignored_not_relevant` | Classificação indicou que o documento não traz dados úteis. |
| `ignored_duplicate` | Hash já processado anteriormente. |
| `needs_ocr` | Texto extraído insuficiente, provável PDF escaneado. |

## Contratos

Os contratos mais importantes ficam em Pydantic:

- `DocumentClassification`: decisão pré-extração.
- `ExtractedMetric`: uma métrica numérica.
- `ExtractedInsight`: um fato documental sem valor numérico obrigatório.
- `ExtractedMetricBatch`: resposta de um documento.
- `ExtractedDocumentMetrics`: resposta de um item no lote.
- `ExtractedBatchResponse`: resposta de vários documentos.

Esses schemas garantem que o payload da LLM seja validado antes de persistir. Métricas sem `value` são rejeitadas na persistência de métricas; informações úteis sem valor numérico devem entrar como `insights`.

## Transações e Erros

Os serviços gravam mudanças de estado em etapas. Na ingestão, o documento é criado depois do download e hash. Na classificação, o status vira `classifying` antes da chamada externa e depois recebe a decisão. Na extração, o lote marca documentos como `processing`; falhas viram `failed` com `error_message` auditável.

Quando a extração em lote não retorna um documento, ou não traz dados, o serviço tenta uma chamada individual de retry. Se o retry também falhar, o documento é marcado como `failed`.

## Normalização

Não confie que o modelo sempre retornará o mesmo nome para uma métrica. `app/modules/metrics/catalog.py` resolve aliases, nome canônico, categoria, unidade/moeda padrão e prioridade de ordenação da camada Gold.

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
