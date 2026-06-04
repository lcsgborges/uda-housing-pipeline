# Testes

Organização por domínio da aplicação:

* `api/`: contratos HTTP e comportamento dos routers.
* `extraction/`: parsing, chunking, contrato semântico, cliente LLM e serviço de extração.
* `ingestion/`: scraping, download, hash, idempotência e serviço de ingestão.
* `lineage/`: repositório e schemas de linhagem.
* `storage/`: storage local/S3 e helpers de URI.
* `fixtures/`: validações de fixtures e exemplos documentais.

O `conftest.py` fica na raiz para compartilhar o PostgreSQL via Testcontainers, a sessão assíncrona e o `TestClient` entre todos os domínios.
