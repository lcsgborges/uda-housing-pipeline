# Módulo de Ingestão

## Responsabilidade

O módulo de ingestão encontra documentos em sites de RI, baixa PDFs novos, evita duplicados e aciona classificação e extração quando configurado.

## Componentes

| Arquivo | Responsabilidade |
| --- | --- |
| `scraper.py` | Busca links candidatos e pontua relevância. |
| `downloader.py` | Baixa bytes do documento. |
| `hashing.py` | Calcula SHA-256. |
| `service.py` | Orquestra empresa -> link -> documento -> classificação -> extração. |
| `scheduler.py` | Executa ciclo diário às 02:00 quando habilitado. |
| `router.py` | Expõe endpoints de ingestão. |

## Idempotência

A idempotência usa `documents.file_hash`.

Fluxo:

1. Baixa o PDF.
2. Calcula SHA-256.
3. Consulta se o hash já existe.
4. Se existir, registra `ignored_duplicate`.
5. Se não existir, salva o arquivo e segue o processamento.

## Saída do Serviço

`IngestionService.run()` retorna contadores simples:

- `companies`: empresas ativas consideradas.
- `discovered`: links PDF candidatos encontrados.
- `processed`: documentos novos baixados e registrados.
- `ignored_duplicates`: documentos rejeitados por hash já conhecido.

`IngestionService.run_scheduled_cycle()` envolve três etapas e retorna um objeto com `ingestion`, `classification` e `extraction`.

## Endpoints

```http
POST /api/ingestion/run
POST /api/ingestion/run/{company_id}
POST /api/ingestion/classify-batch?batch_size=10
POST /api/ingestion/extract-batch?batch_size=10
```

## Scheduler

Para habilitar o ciclo diário junto com a API:

```bash
ENABLE_INGESTION_SCHEDULER=true uv run uvicorn app.main:app --reload
```

Use `INGESTION_SCHEDULE_HOUR`, `INGESTION_SCHEDULE_MINUTE` e `SCHEDULER_TIMEZONE`
para controlar o horário diário.
