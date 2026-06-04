# Arquitetura

## Visão Geral

A aplicação é uma API FastAPI com módulos de domínio separados por responsabilidade. O banco relacional guarda catálogo, status de processamento, métricas e linhagem. O storage guarda os arquivos baixados localmente ou em RustFS compatível com S3.

![Pipeline UDA — Fluxo](../assets/pipeline.png)

> Figura: Fluxo do pipeline UDA — ingestão, storage (local/RustFS), extração (PDF parser, chunking, LLM), contrato Pydantic, catálogo de métricas, persistência (PostgreSQL) e API FastAPI.

## Camadas

| Camada | Responsabilidade | Código |
| --- | --- | --- |
| Configuração | Settings, banco, logging e utilitários | `app/core` |
| API | Routers FastAPI por módulo | `app/modules/*/router.py` |
| Serviço | Regras de negócio e orquestração | `app/modules/*/service.py` |
| Repositório | Acesso ao banco via SQLAlchemy | `app/modules/*/repository.py` |
| Modelos | Entidades SQLAlchemy | `app/modules/*/models.py` |
| Schemas | Entrada/saída Pydantic | `app/modules/*/schemas.py` |
| Orquestração | Scheduler interno diário e endpoints manuais | `app/modules/ingestion` |

## Decisões Técnicas

### FastAPI

Escolhida por ser direta para APIs REST, documentação OpenAPI automática e boa integração com Pydantic.

### SQLAlchemy Async

O projeto usa `AsyncSession` e `asyncpg` para PostgreSQL. Isso mantém consistência com FastAPI assíncrono e facilita testes com Testcontainers.

### Pydantic v2

Usado para validar entrada de API e, principalmente, o contrato de saída da LLM. A extração só entra no banco se aderir ao schema.

### LLM Providers

A extração usa contrato Pydantic antes da persistência. Com `openai`, documentos
pendentes são agrupados por lote. Com `ollama`, cada documento é enviado ao
servidor local sequencialmente.

### RustFS / S3 Compatível

O storage pode ser local no desenvolvimento ou RustFS no Compose. O banco guarda apenas metadados e URI do objeto.

## Camada Gold

Inspirado em arquitetura Medallion, o projeto mantém duas leituras:

- `/api/metrics`: visão bruta e auditável das métricas persistidas.
- `/api/conjuntura`: visão final deduplicada, escolhendo a melhor evidência para cada métrica canônica.

Essa separação evita perder rastreabilidade e ainda oferece uma saída pronta para consumo analítico.
