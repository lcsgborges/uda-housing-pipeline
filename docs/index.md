# Housing Data Intelligence

Documentação técnica do pipeline UDA para análise de dados não estruturados no domínio de conjuntura habitacional.

O projeto transforma PDFs de Relações com Investidores e boletins de conjuntura em métricas estruturadas, auditáveis e consultáveis por API. A extração usa LLM com contrato Pydantic, catálogo canônico de métricas, persistência relacional e linhagem da evidência original.

## O Que Este Projeto Entrega

- Coleta documentos em fontes de RI cadastradas por empresa.
- Baixa PDFs, calcula hash e evita reprocessamento de duplicados.
- Extrai texto dos PDFs com PyMuPDF.
- Seleciona contexto por full scan ou chunking semântico.
- Envia contexto para LLM com Structured Outputs.
- Valida a resposta com Pydantic.
- Normaliza métricas por vocabulário controlado.
- Persiste métricas, documentos e linhagem em PostgreSQL.
- Expõe APIs para consulta de empresas, documentos, métricas e conjuntura.
- Orquestra ingestão e extração por API, scheduler ou DAG do Airflow.

## Caminho Recomendado

1. Leia [Objetivo e Escopo](projeto/objetivo.md) para entender o problema.
2. Veja [Arquitetura](projeto/arquitetura.md) e [Fluxo de Dados](projeto/fluxo-de-dados.md).
3. Configure o ambiente em [Configuração](ambiente/configuracao.md).
4. Rode a API seguindo [Executar Localmente](ambiente/execucao-local.md) ou [Docker Compose](como_rodar_com_compose.md).
5. Consulte [Testes](ambiente/testes.md) antes de alterar o comportamento.

## Principais Endpoints

| Endpoint | Uso |
| --- | --- |
| `GET /health` | Verifica saúde da API. |
| `POST /api/companies` | Cadastra empresa e URL de RI. |
| `POST /api/ingestion/run` | Executa descoberta, download e extração. |
| `POST /api/ingestion/extract-batch` | Processa documentos pendentes em lote. |
| `GET /api/documents` | Lista documentos coletados. |
| `GET /api/metrics` | Lista métricas extraídas em visão bruta. |
| `GET /api/conjuntura` | Retorna camada final deduplicada por métrica. |

## Comandos Rápidos

```bash
uv sync --extra dev
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests
uv run --extra dev mkdocs serve
```
