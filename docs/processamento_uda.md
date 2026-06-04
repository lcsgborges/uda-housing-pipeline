# Processamento UDA e API

Este projeto usa uma implementação nativa de UDA em Python. A extração de valores não é feita por regex, coordenadas fixas de PDF ou regras de layout. Regras tradicionais aparecem apenas em etapas auxiliares, como segmentação de texto e controle de idempotência; a interpretação dos dados é feita pelo LLM e validada por contrato Pydantic.

## B. Processamento dos dados

### 1. Parsing e segmentação

O parser usa `PyMuPDF` para abrir o PDF e extrair texto por blocos ordenados:

- arquivos curtos seguem em modo `full_scan`;
- arquivos longos seguem em modo `semantic_chunking`;
- o texto é dividido por seções/títulos, blocos e limite de caracteres;
- os chunks recebem metadados de página, título/section heading, tags semânticas e score de relevância;
- a seleção de chunks prioriza trechos com sinais operacionais, financeiros, temporais e tabulares.

O objetivo do chunking é reduzir custo e latência do LLM. Ele não extrai métricas por conta própria.

Arquivos principais:

- `app/modules/extraction/pdf_parser.py`
- `app/modules/extraction/chunking.py`
- `app/modules/extraction/service.py`

### 2. Extração

A pilha escolhida é solução nativa:

- `PyMuPDF` para parsing;
- motor próprio de chunking semântico;
- OpenAI Responses API para extração;
- `Pydantic` como contrato de saída estruturada.

O prompt instrui o modelo a:

- extrair apenas métricas explicitamente suportadas pelo contexto;
- priorizar valores absolutos em relatórios de RI;
- aceitar percentuais quando o documento for boletim/tabela comparativa;
- usar `null` para ausentes;
- informar página e trecho de evidência sempre que possível;
- retornar nomes de métricas em `snake_case`.

Arquivos principais:

- `app/modules/extraction/llm_client.py`
- `app/modules/metrics/schemas.py`

### 3. Contrato semântico

O contrato semântico é definido por `ExtractedMetric`, `ExtractedMetricBatch` e `ExtractedBatchResponse`.

Validações relevantes:

- `metric_name` deve estar em `snake_case`;
- `period_quarter` precisa estar entre 1 e 4;
- `period_year`, quando presente, precisa estar em faixa plausível;
- `confidence` precisa estar entre 0 e 1;
- `source_page`, quando presente, precisa ser positiva;
- campos textuais possuem limites de tamanho.

Se a OpenAI retornar um payload fora do contrato, a validação falha antes de gravar no banco.

## C. Camada de serviço

A API REST disponibiliza consultas por empresa e período.

Endpoints principais:

- `GET /api/conjuntura?empresa=MRV&ano=2025&trimestre=3`
- `GET /api/metrics?empresa=MRV&ano=2025&trimestre=3&metrica=vendas_liquidas`
- `GET /api/documents`

O endpoint de conjuntura resolve empresa por nome ou ticker e retorna métricas com fonte, página, trecho e confiança.
