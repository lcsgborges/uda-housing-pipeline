from app.modules.metrics.schemas import ExtractedMetricBatch


def get_semantic_contract_json_schema() -> dict:
    return ExtractedMetricBatch.model_json_schema()
