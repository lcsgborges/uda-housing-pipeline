# Fluxo de Dados

Esta página descreve a passagem dos dados pelo pipeline. Para a visão de operação
com estados, Batch API e componentes de runtime, consulte
[Operação do Pipeline](operacao.md).

## 1. Cadastro de Empresas

Empresas são cadastradas com nome, ticker e URL de Relações com Investidores.

Código principal:

- `app/modules/companies/router.py`
- `app/modules/companies/service.py`
- `app/modules/companies/repository.py`
- `app/modules/companies/models.py`

## 2. Descoberta de Documentos

O scraper visita a página de RI e pontua links candidatos. Links mais relevantes costumam conter termos como resultado, prévia, release, ITR/DFP, trimestre e PDF.

Quando os documentos estão no HTML, a coleta usa os `<a href>` da página e ignora regiões de navegação para evitar links institucionais. Quando a página usa File Manager da MZiQ, como a Central de Resultados da MRV, o HTML traz apenas a configuração JavaScript. Nesse caso o scraper extrai `fmId`, `fmBase`, idioma e categorias, chama a API MZiQ e coleta os metadados publicados de todos os anos disponíveis.

Na central de resultados MZiQ, a busca automática considera as categorias de release/resultados, prévia operacional e ITR/DFP. Planilhas, áudios e transcrições não entram nesse caminho, porque a ingestão baixa PDFs para classificação e extração.

Código principal:

- `app/modules/ingestion/scraper.py`

## 3. Download e Idempotência

O downloader baixa o documento, calcula SHA-256 e consulta documentos já registrados. Se o hash já existe, o novo registro é marcado como `ignored_duplicate`.

Se o hash não existir, o serviço salva o PDF no backend configurado, infere ano,
trimestre e tipo documental a partir de URL/título quando possível, e cria o
registro `downloaded` em `documents`.

Código principal:

- `app/modules/ingestion/downloader.py`
- `app/modules/ingestion/hashing.py`
- `app/modules/ingestion/service.py`

## 4. Storage

O conteúdo do PDF é gravado em storage local ou RustFS. A tabela `documents` guarda a URI em `local_path`.

Backends:

- `local`: grava no diretório definido por `DOCUMENTS_DIR`.
- `rustfs`: grava em bucket S3 compatível e persiste URI `s3://bucket/key`.

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

Além do status, a etapa persiste metadados como confiança, motivo, domínios
detectados, modelo de classificação, período inferido e estratégia de extração.

Código principal:

- `app/modules/classification/service.py`
- `app/modules/classification/schemas.py`

## 6. Parsing e Contexto de Extração

Somente documentos em `classified_useful` seguem para extração. O parser extrai texto por página com PyMuPDF. Depois o serviço decide entre:

- `full_scan`: documentos curtos entram completos em uma chamada.
- `sequential_scan`: documentos longos são quebrados em partes sequenciais e todas as partes são enviadas à LLM.

O `sequential_scan` analisa o documento inteiro sem montar um prompt único gigante. Cada parte respeita `EXTRACTION_CONTEXT_MAX_CHARS`; as respostas são consolidadas e deduplicadas antes da persistência. Se uma parte falhar, o documento inteiro fica `failed` para manter a auditoria honesta.

Código principal:

- `app/modules/extraction/pdf_parser.py`
- `app/modules/extraction/chunking.py`
- `app/modules/extraction/service.py`

## 7. Extração por LLM

O cliente LLM recebe o contexto, metadados do documento e o catálogo canônico de métricas. A resposta precisa obedecer ao contrato Pydantic.

O contrato permite duas saídas:

- métricas numéricas, persistidas em `metrics`;
- insights/fatos documentais, persistidos em `document_insights`.

Com `LLM_PROVIDER=openai`, o serviço pode usar extração síncrona pela Responses API ou submissão offline pela OpenAI Batch API. No modo Batch API, cada parte do documento vira uma linha JSONL com `custom_id`, e o resultado é importado depois do status `completed`. Com `LLM_PROVIDER=ollama`, a interface de lote percorre os documentos sequencialmente no servidor local.

No modo OpenAI Batch API:

1. `submit` seleciona documentos úteis e gera uma request `/v1/responses` por parte.
2. O arquivo JSONL é enviado pela Files API com `purpose=batch`.
3. O batch é criado com janela `24h`.
4. Os documentos selecionados ficam `processing`.
5. `GET /openai-batch/{batch_id}` consulta o status.
6. `import` só persiste resultados quando o batch está `completed`.
7. Se houver erro ou parte faltante, o documento afetado vira `failed`.

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

## 10. Estados Operacionais

| Status | Entrada principal | Próximo passo comum |
| --- | --- | --- |
| `downloaded` | PDF novo salvo | Classificação. |
| `classifying` | Lote de classificação iniciado | Decisão de utilidade. |
| `classified_useful` | Documento aprovado | Extração síncrona ou Batch API. |
| `processing` | Extração iniciada ou batch submetido | Persistência ou falha. |
| `processed` | Métricas ou insights salvos | Consulta. |
| `ignored_duplicate` | Hash já conhecido | Fim. |
| `ignored_not_relevant` | LLM classificou como irrelevante | Fim. |
| `needs_ocr` | Texto insuficiente | OCR futuro. |
| `failed` | Erro auditável | Investigação ou reprocessamento manual. |
