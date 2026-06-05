# Módulo de Ingestão

## Responsabilidade

O módulo de ingestão encontra documentos em sites de RI, baixa PDFs novos, evita duplicados e aciona classificação e extração quando configurado.

O scraper trabalha em duas camadas:

1. Lê links estáticos do HTML e aceita PDFs diretos ou URLs de gerenciadores de arquivo conhecidos.
2. Quando a página usa File Manager da MZiQ, extrai `fmId`, `fmBase`, idioma e categorias declaradas no JavaScript da página. Em páginas de central de resultados, busca as categorias de resultado, prévia operacional e ITR/DFP no endpoint `/filter/categories/meta`, que retorna documentos de todos os anos publicados.

Essa segunda camada é necessária porque páginas como a Central de Resultados da MRV não renderizam os documentos no HTML inicial. A tabela de anos e trimestres é montada no navegador por chamada POST à API da MZiQ. Sem essa chamada, o sistema veria apenas links de navegação e perderia os PDFs dos anos anteriores.

## Componentes

| Arquivo | Responsabilidade |
| --- | --- |
| `scraper.py` | Busca links candidatos no HTML e no File Manager MZiQ, deduplica URLs e pontua relevância. |
| `downloader.py` | Baixa bytes do documento. |
| `hashing.py` | Calcula SHA-256. |
| `service.py` | Orquestra empresa -> link -> documento -> classificação -> extração. |
| `scheduler.py` | Executa ciclo diário às 02:00 quando habilitado. |
| `router.py` | Expõe endpoints de ingestão. |

## Descoberta de Links

`RIScraper.find_pdf_links()` recebe a URL de RI cadastrada para a empresa e retorna uma lista de dicionários com `url`, `title` e `score`.

Fluxo interno:

1. Faz `GET` da página com `httpx`, `User-Agent` configurável e redirects habilitados.
2. Usa BeautifulSoup para localizar `<a href>`.
3. Ignora links dentro de `header`, `footer`, `nav` e contêineres de navegação para evitar documentos de menu, como ESG institucional.
4. Aceita links diretos `.pdf` e URLs `api.mziq.com/mzfilemanager`.
5. Se a página declarar `fmId` e `fmBase`, procura blocos `categories.push(...)`.
6. Seleciona, na ordem da tabela, até três categorias de documentos de resultado: release/resultados, prévia operacional e ITR/DFP. Categorias de planilha, áudio e transcrição ficam fora dessa busca automática.
7. Chama `POST {fmBase}/company/{fmId}/filter/categories/meta` com `categoryInternalNames`, `language` e `published=true`.
8. Lê `data.document_metas`, escolhe `link_url`, `permalink` ou `file_url`, deduplica por URL e monta título com tipo e período.
9. Ordena os links por pontuação antes de devolver ao serviço. Documentos MZiQ selecionados recebem a mesma pontuação para preservar a ordem publicada pela própria API.

Para a MRV, a página `https://ri.mrv.com.br/informacoes-financeiras/central-de-resultados/` declara categorias como `central_de_resultados_release`, `central_de_resultados_previa` e `central_de_resultados_itr`. A API retorna anos publicados de 2026 até 2006, incluindo os PDFs dos trimestres que não aparecem no HTML estático.

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
POST /api/ingestion/classify-batch?batch_size=5
POST /api/ingestion/extract-batch?batch_size=1
POST /api/ingestion/openai-batch/submit?batch_size=1
GET /api/ingestion/openai-batch/{batch_id}
POST /api/ingestion/openai-batch/{batch_id}/import
```

## Scheduler

Para habilitar o ciclo diário junto com a API:

```bash
ENABLE_INGESTION_SCHEDULER=true uv run uvicorn app.main:app --reload
```

Use `INGESTION_SCHEDULE_HOUR`, `INGESTION_SCHEDULE_MINUTE` e `SCHEDULER_TIMEZONE`
para controlar o horário diário.
