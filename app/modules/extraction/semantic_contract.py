from app.modules.metrics.schemas import ExtractedBatchResponse, ExtractedMetricBatch


def get_semantic_contract_json_schema() -> dict:
    """Retorna o JSON Schema do contrato de extração de um documento."""
    return ExtractedMetricBatch.model_json_schema()


def get_semantic_batch_contract_json_schema() -> dict:
    """Retorna o JSON Schema do contrato de extração em lote."""
    return ExtractedBatchResponse.model_json_schema()
