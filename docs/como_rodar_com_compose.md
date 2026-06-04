# Como rodar com Docker Compose

Este projeto sobe a API FastAPI e o RustFS em uma única stack. A API usa SQLite em volume para o catálogo relacional e RustFS como storage S3-compatible para PDFs/imagens coletados.

## 1. Configurar ambiente

```bash
cp .env.example .env
```

Edite `.env` e preencha:

```bash
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
```

Para rodar sem custo de API durante desenvolvimento:

```bash
LLM_PROVIDER=fake
```

## 2. Subir a stack

```bash
docker compose --env-file .env up --build
```

Serviços expostos:

- API: `http://localhost:8000`
- Swagger/OpenAPI: `http://localhost:8000/docs`
- RustFS S3 API: `http://localhost:9000`
- RustFS Console: `http://localhost:9001`

Credenciais locais do RustFS:

```bash
RUSTFS_ACCESS_KEY=rustfsadmin
RUSTFS_SECRET_KEY=rustfsadmin
```

## 3. Validar saúde

```bash
curl "http://localhost:8000/health"
```

Resposta esperada:

```json
{"status":"ok"}
```

## 4. Cadastrar uma empresa

```bash
curl -X POST "http://localhost:8000/api/companies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MRV",
    "ticker": "MRVE3",
    "ri_url": "https://ri.mrv.com.br",
    "is_active": true
  }'
```

## 5. Rodar ingestão e extração

```bash
curl -X POST "http://localhost:8000/api/ingestion/run"
```

O fluxo baixa PDFs novos, calcula SHA-256, ignora duplicados, grava o arquivo no RustFS e chama a OpenAI para extrair métricas estruturadas.

## 6. Consultar resultados

```bash
curl "http://localhost:8000/api/documents"
curl "http://localhost:8000/api/metrics"
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
```

## 7. Modo contínuo

No `.env`, habilite:

```bash
ENABLE_INGESTION_SCHEDULER=true
INGESTION_POLL_INTERVAL_MINUTES=1440
```

Depois reinicie:

```bash
docker compose --env-file .env up --build
```

## 8. Parar e limpar

Parar containers:

```bash
docker compose down
```

Parar e remover volumes persistidos:

```bash
docker compose down -v
```
