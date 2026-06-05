class _FakeExtractionService:
    async def process_pending_documents_batch(self, batch_size):
        return {"selected": batch_size, "processed": batch_size, "failed": 0}


class _FakeClassificationService:
    async def process_pending_documents_batch(self, batch_size):
        return {
            "selected": batch_size,
            "useful": batch_size,
            "ignored": 0,
            "needs_ocr": 0,
            "failed": 0,
        }


class _FakeIngestionService:
    def __init__(self, session=None):
        self.session = session
        self.classification_service = _FakeClassificationService()
        self.extraction_service = _FakeExtractionService()

    async def run(self, company_id=None):
        return {
            "companies": 1 if company_id else 2,
            "discovered": 3,
            "processed": 2,
            "ignored_duplicates": 1,
        }

    async def run_scheduled_cycle(self, company_id=None):
        return {
            "ingestion": await self.run(company_id=company_id),
            "classification": {
                "batches": 1,
                "selected": 2,
                "useful": 2,
                "ignored": 0,
                "needs_ocr": 0,
                "failed": 0,
            },
            "extraction": {"batches": 1, "selected": 2, "processed": 2, "failed": 0},
        }


def test_ingestion_router_executa_fluxos(client):
    from app.main import app
    from app.modules.ingestion.router import get_service

    app.dependency_overrides[get_service] = lambda: _FakeIngestionService()
    try:
        run_all = client.post("/api/ingestion/run")
        run_company = client.post("/api/ingestion/run/7")
        classify_batch = client.post("/api/ingestion/classify-batch", params={"batch_size": 3})
        extract_batch = client.post("/api/ingestion/extract-batch", params={"batch_size": 4})
    finally:
        app.dependency_overrides.pop(get_service, None)

    assert run_all.status_code == 200
    assert run_all.json()["ingestion"]["companies"] == 2
    assert run_company.status_code == 200
    assert run_company.json()["ingestion"]["companies"] == 1
    assert classify_batch.status_code == 200
    assert classify_batch.json() == {
        "selected": 3,
        "useful": 3,
        "ignored": 0,
        "needs_ocr": 0,
        "failed": 0,
    }
    assert extract_batch.status_code == 200
    assert extract_batch.json() == {"selected": 4, "processed": 4, "failed": 0}


def test_get_service_constroi_ingestion_service(monkeypatch):
    from app.modules.ingestion import router as ingestion_router

    monkeypatch.setattr(ingestion_router, "IngestionService", _FakeIngestionService)

    service = ingestion_router.get_service(session="session")

    assert isinstance(service, _FakeIngestionService)
    assert service.session == "session"
