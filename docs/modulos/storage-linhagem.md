# Storage e Linhagem

## Storage

O projeto separa arquivo bruto e metadados:

- o PDF fica em storage local ou RustFS;
- o banco guarda URI, hash, status e metadados do documento.

## Backends

### Local

```env
STORAGE_BACKEND=local
DOCUMENTS_DIR=./data/documents
```

### RustFS

```env
STORAGE_BACKEND=rustfs
RUSTFS_ENDPOINT=localhost:9000
RUSTFS_ACCESS_KEY=rustfsadmin
RUSTFS_SECRET_KEY=rustfsadmin
RUSTFS_BUCKET=uda-documents
RUSTFS_SECURE=false
```

## Linhagem

Para cada métrica persistida, o sistema cria um registro em `data_lineage`. Insights guardam sua própria evidência em `source_page` e `source_excerpt`, mas não geram registro em `data_lineage` nesta versão.

Campos principais:

- `metric_id`
- `document_id`
- `original_url`
- `file_hash`
- `source_page`
- `source_excerpt`
- `extraction_model`
- `extraction_prompt_version`
- `extracted_at`

## Por Que Isso Importa

A extração com LLM precisa ser auditável. A linhagem permite conferir de onde uma métrica veio e qual modelo/prompt produziu o valor.

## Consulta

Hoje a linhagem é persistida junto das métricas e pode ser consultada por repositório/serviço. Um endpoint específico de linhagem é um próximo passo natural.
