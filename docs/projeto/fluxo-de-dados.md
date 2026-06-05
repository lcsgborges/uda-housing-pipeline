# Fluxo de Dados

## 1. Cadastro de Empresas

Empresas são cadastradas com nome, ticker e URL de Relações com Investidores.

Código principal:

- `app/modules/companies/router.py`
- `app/modules/companies/service.py`
- `app/modules/companies/repository.py`
- `app/modules/companies/models.py`

## 2. Descoberta de Documentos

O scraper visita a página de RI e pontua links candidatos. Links mais relevantes costumam conter termos como resultado, prévia, release, trimestre e PDF.

Código principal:

- `app/modules/ingestion/scraper.py`

## 3. Download e Idempotência

O downloader baixa o documento, calcula SHA-256 e consulta documentos já registrados. Se o hash já existe, o novo registro é marcado como `ignored_duplicate`.

Código principal:

- `app/modules/ingestion/downloader.py`
- `app/modules/ingestion/hashing.py`
- `app/modules/ingestion/service.py`

## 4. Storage

O conteúdo do PDF é gravado em storage local ou RustFS. A tabela `documents` guarda a URI em `local_path`.

Backends:

- `local`: grava no diretório definido por `DOCUMENTS_DIR`.
- `rustfs`: grava em bucket S3 compatível.

Código principal:

- `app/modules/storage/service.py`

## 5. Classificação

Antes da extração completa, o sistema classifica o documento. Essa etapa reduz custo e ruído porque evita enviar documentos institucionais, avisos legais ou PDFs sem texto útil para a extração de métricas.

Fluxo da classificação:

1. Lê o PDF a partir de `local_path` ou URI de storage.
2. Extrai texto por página com PyMuPDF.
3. Detecta PDFs provavelmente escaneados quando há pouco texto extraído.
4. Monta uma amostra com páginas iniciais e chunks relevantes.
5. Envia a amostra para a LLM com o contrato `DocumentClassification`.
6. Atualiza o documento para `classified_useful`, `ignored_not_relevant`, `needs_ocr` ou `failed`.

Código principal:

- `app/modules/classification/service.py`
- `app/modules/classification/schemas.py`

## 6. Parsing e Contexto de Extração

Somente documentos em `classified_useful` seguem para extração. O parser extrai texto por página com PyMuPDF. Depois o serviço decide entre:

- `full_scan`: documentos curtos entram completos no contexto.
- `semantic_chunking`: documentos longos são quebrados em chunks e ranqueados.

Código principal:

- `app/modules/extraction/pdf_parser.py`
- `app/modules/extraction/chunking.py`
- `app/modules/extraction/service.py`

## 7. Extração por LLM

O cliente LLM recebe o contexto, metadados do documento e o catálogo canônico de métricas. A resposta precisa obedecer ao contrato Pydantic.

O contrato permite duas saídas:

- métricas numéricas, persistidas em `metrics`;
- insights/fatos documentais, persistidos em `document_insights`.

Com `LLM_PROVIDER=openai`, o serviço envia vários documentos em uma única chamada de extração. Com `LLM_PROVIDER=ollama`, a interface de lote percorre os documentos sequencialmente.

Código principal:

- `app/modules/extraction/llm_client.py`
- `app/modules/extraction/semantic_contract.py`
- `app/modules/metrics/schemas.py`

## 8. Normalização e Persistência

Antes de salvar, o serviço:

- normaliza `metric_name` por alias;
- preenche categoria, unidade e moeda quando o catálogo permite;
- mantém `null` para valores realmente ausentes;
- descarta métricas sem `value`, mas preserva insights sem valor numérico;
- cria registros de linhagem para cada métrica.

Código principal:

- `app/modules/metrics/catalog.py`
- `app/modules/extraction/service.py`
- `app/modules/insights/models.py`
- `app/modules/lineage/models.py`

## 9. Consulta

As consultas são expostas pela API:

- `/api/metrics`: dados brutos.
- `/api/conjuntura`: visão deduplicada por métrica canônica.
- `/api/insights`: fatos, metas, ações, riscos e explicações extraídos.
- `/api/documents`: documentos e status.
