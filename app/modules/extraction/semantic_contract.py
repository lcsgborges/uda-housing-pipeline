from app.modules.metrics.schemas import ExtractedBatchResponse, ExtractedMetricBatch


def get_semantic_contract_json_schema() -> dict:
    return ExtractedMetricBatch.model_json_schema()


def get_semantic_batch_contract_json_schema() -> dict:
    return ExtractedBatchResponse.model_json_schema()
