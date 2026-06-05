# Arquitetura

## Visão Geral

A aplicação é uma API FastAPI com módulos de domínio separados por responsabilidade. O banco relacional guarda empresas, documentos, classificação, métricas, insights e linhagem. O storage guarda os PDFs baixados localmente ou em RustFS compatível com S3.

![Pipeline UDA — Fluxo](../assets/pipeline.png)

> Figura: Fluxo do pipeline UDA — ingestão, storage (local/RustFS), classificação, extração (PDF parser, chunking, LLM), contrato Pydantic, catálogo de métricas, persistência (PostgreSQL) e API FastAPI.

## Camadas

| Camada | Responsabilidade | Código |
| --- | --- | --- |
| Configuração | Settings por `.env`, engine SQLAlchemy, sessão, logging e utilitários | `app/core` |
| API | Routers FastAPI e injeção de dependências por módulo | `app/modules/*/router.py` |
| Serviço | Regras de negócio, transições de estado e orquestração | `app/modules/*/service.py` |
| Repositório | Acesso ao banco via SQLAlchemy assíncrono | `app/modules/*/repository.py` |
| Modelos | Entidades SQLAlchemy e relacionamentos | `app/modules/*/models.py` |
| Schemas | Contratos Pydantic de API, classificação e extração | `app/modules/*/schemas.py` |
| Orquestração | Scheduler diário e endpoints manuais de lote | `app/modules/ingestion` |

## Como o Código Está Organizado

`app/main.py` cria a aplicação FastAPI, registra routers e controla o ciclo de vida. Se `ENABLE_INGESTION_SCHEDULER=true`, o `lifespan` inicia o scheduler ao subir a API e o encerra no shutdown.

`app/core/config.py` centraliza as configurações em uma classe `Settings` baseada em `pydantic-settings`. O restante do sistema acessa essas configurações por `get_settings()`, que é cacheado e também cria o diretório local de documentos quando necessário.

Os módulos de domínio seguem o mesmo desenho:

- `router.py` recebe HTTP e instancia serviços por `Depends`.
- `service.py` concentra regra de negócio e coordena repositórios, storage, parser e LLM.
- `repository.py` isola consultas e persistência com `AsyncSession`.
- `models.py` define tabelas SQLAlchemy.
- `schemas.py` define contratos Pydantic de entrada e saída.

Módulos técnicos, como `storage` e `extraction`, não seguem CRUD completo porque encapsulam integrações e processamento.

## Decisões Técnicas

### FastAPI

Escolhida por ser direta para APIs REST, documentação OpenAPI automática e boa integração com Pydantic.

### SQLAlchemy Async

O projeto usa `AsyncSession` e `asyncpg` para PostgreSQL. Isso mantém consistência com FastAPI assíncrono e facilita testes com Testcontainers.

### Pydantic v2

Usado para validar entrada de API e, principalmente, o contrato de saída da LLM. A extração só entra no banco se aderir ao schema.

### Classificação Antes da Extração

O pipeline não envia todo PDF novo diretamente para a extração cara. `ClassificationService` lê uma amostra do documento, detecta PDFs com texto insuficiente e usa a LLM para decidir se o material é útil. A decisão atualiza campos como `classification_is_useful`, `classification_confidence`, `detected_domains`, `extraction_strategy` e `classified_at`.

Documentos úteis recebem `classified_useful`; documentos irrelevantes recebem `ignored_not_relevant`; PDFs provavelmente escaneados recebem `needs_ocr`.

### LLM Providers

A classificação e a extração usam contrato Pydantic antes da persistência. Com `openai`, a extração de documentos pendentes é agrupada em lote usando Structured Outputs. Com `ollama`, a chamada de lote é implementada como processamento sequencial no servidor local.

As respostas podem conter duas camadas:

- `metrics`: valores numéricos explícitos que entram em `metrics`.
- `insights`: fatos documentais qualitativos ou textuais que entram em `document_insights`.

### RustFS / S3 Compatível

O storage pode ser local no desenvolvimento ou RustFS no Compose. O banco guarda apenas metadados e URI do objeto.

## Persistência

O PostgreSQL mantém:

- `companies`: empresas monitoradas.
- `documents`: PDFs encontrados, hash, URI, status e metadados de classificação.
- `metrics`: métricas extraídas, normalizadas e filtráveis.
- `document_insights`: fatos, metas, riscos, ações e resumos sem valor numérico obrigatório.
- `data_lineage`: evidência de cada métrica, incluindo documento, hash, página, trecho, modelo e versão de prompt.

## Camada Gold

Inspirado em arquitetura Medallion, o projeto mantém duas leituras:

- `/api/metrics`: visão bruta e auditável das métricas persistidas.
- `/api/conjuntura`: visão final deduplicada, escolhendo a melhor evidência para cada métrica canônica.

Essa separação evita perder rastreabilidade e ainda oferece uma saída pronta para consumo analítico.
