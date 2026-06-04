# Testes

Organizacao por dominio da aplicacao:

- `api/`: contratos HTTP e comportamento dos routers.
- `extraction/`: parsing, chunking, contrato semantico, cliente LLM e servico de extracao.
- `ingestion/`: scraping, download, hash, idempotencia e servico de ingestao.
- `lineage/`: repositorio e schemas de linhagem.
- `storage/`: storage local/S3 e helpers de URI.
- `fixtures/`: validacoes de fixtures e exemplos documentais.

O `conftest.py` fica na raiz para compartilhar o PostgreSQL via Testcontainers, sessao async
e `TestClient` entre todos os dominios.
