# Housing Data Intelligence

Documentação técnica do pipeline UDA para análise de dados não estruturados no domínio de conjuntura habitacional.

O projeto transforma PDFs de Relações com Investidores, relatórios de sustentabilidade e boletins de conjuntura em métricas e insights estruturados, auditáveis e consultáveis por API. O pipeline usa uma classificação barata antes da extração, contrato Pydantic para a saída da LLM, catálogo canônico de métricas, persistência relacional e linhagem da evidência original.

## Autoria e Repositório

- Autor: Lucas Guimarães Borges
- E-mail: [lcsgborges@gmail.com](mailto:lcsgborges@gmail.com)
- GitHub: [lcsgborges](https://github.com/lcsgborges)
- Repositório: [lcsgborges/uda-housing-pipeline](https://github.com/lcsgborges/uda-housing-pipeline)

## O Que Este Projeto Entrega

- Coleta documentos em fontes de RI cadastradas por empresa.
- Baixa PDFs, calcula hash e evita reprocessamento de duplicados.
- Extrai texto dos PDFs com PyMuPDF.
- Classifica documentos como úteis, irrelevantes ou dependentes de OCR.
- Seleciona contexto por full scan ou varredura sequencial completa.
- Envia contexto para LLM via Ollama local ou OpenAI Structured Outputs.
- Valida a resposta com Pydantic.
- Normaliza métricas por vocabulário controlado.
- Persiste documentos, métricas, insights e linhagem em PostgreSQL.
- Expõe APIs para consulta de empresas, documentos, métricas, insights e conjuntura.
- Orquestra ingestão, classificação e extração por API ou scheduler interno diário.

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
| `POST /api/ingestion/run` | Executa descoberta, download, classificação e extração. |
| `POST /api/ingestion/classify-batch` | Classifica documentos baixados. |
| `POST /api/ingestion/extract-batch` | Processa documentos pendentes em lote. |
| `POST /api/ingestion/openai-batch/submit` | Submete extração offline pela OpenAI Batch API. |
| `GET /api/ingestion/openai-batch/{batch_id}` | Consulta status do batch OpenAI. |
| `POST /api/ingestion/openai-batch/{batch_id}/import` | Importa resultados do batch OpenAI concluído. |
| `GET /api/documents` | Lista documentos coletados. |
| `GET /api/metrics` | Lista métricas extraídas em visão bruta. |
| `GET /api/insights` | Lista fatos, metas, riscos e ações documentais. |
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
uv run task lint
uv run task mkdocs_build
```
