# Módulo de Ingestão

## Responsabilidade

O módulo de ingestão encontra documentos em sites de RI, baixa PDFs novos, evita duplicados e dispara a extração quando configurado.

## Componentes

| Arquivo | Responsabilidade |
| --- | --- |
| `scraper.py` | Busca links candidatos e pontua relevância. |
| `downloader.py` | Baixa bytes do documento. |
| `hashing.py` | Calcula SHA-256. |
| `service.py` | Orquestra empresa -> link -> documento -> extração. |
| `scheduler.py` | Executa ciclo contínuo quando habilitado. |
| `router.py` | Expõe endpoints de ingestão. |

## Idempotência

A idempotência usa `documents.file_hash`.

Fluxo:

1. Baixa o PDF.
2. Calcula SHA-256.
3. Consulta se o hash já existe.
4. Se existir, registra `ignored_duplicate`.
5. Se não existir, salva o arquivo e segue o processamento.

## Endpoints

```http
POST /api/ingestion/run
POST /api/ingestion/run/{company_id}
POST /api/ingestion/extract-batch?batch_size=10
```

## Scheduler

Para habilitar observação contínua junto com a API:

```bash
ENABLE_INGESTION_SCHEDULER=true uv run uvicorn app.main:app --reload
```

Use `INGESTION_POLL_INTERVAL_MINUTES` para controlar o intervalo.
