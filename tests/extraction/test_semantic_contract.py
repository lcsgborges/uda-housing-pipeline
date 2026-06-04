import pytest
from pydantic import ValidationError

from app.modules.extraction.semantic_contract import (
    get_semantic_batch_contract_json_schema,
    get_semantic_contract_json_schema,
)
from app.modules.metrics.schemas import ExtractedMetricBatch


def test_schema_valido():
    payload = {
        "metrics": [
            {
                "company": "MRV",
                "period_year": 2025,
                "period_quarter": 3,
                "metric_name": "vendas_liquidas",
                "metric_category": "operacional",
                "value": 10.0,
                "unit": "R$",
                "currency": "BRL",
                "source_page": 1,
                "source_excerpt": "Vendas líquidas totalizaram 10.",
                "confidence": 0.8,
            }
        ]
    }
    result = ExtractedMetricBatch.model_validate(payload)
    assert result.metrics[0].metric_name == "vendas_liquidas"


def test_schema_rejeita_confianca_invalida():
    payload = {
        "metrics": [
            {
                "company": "MRV",
                "metric_name": "vendas_liquidas",
                "confidence": 1.5,
            }
        ]
    }
    with pytest.raises(ValidationError):
        ExtractedMetricBatch.model_validate(payload)


def test_schema_rejeita_nome_de_metrica_fora_do_padrao():
    payload = {
        "metrics": [
            {
                "company": "MRV",
                "metric_name": "Vendas Líquidas",
                "confidence": 0.8,
            }
        ]
    }
    with pytest.raises(ValidationError):
        ExtractedMetricBatch.model_validate(payload)


def test_schema_rejeita_pagina_invalida():
    payload = {
        "metrics": [
            {
                "company": "MRV",
                "metric_name": "vendas_liquidas",
                "source_page": 0,
                "confidence": 0.8,
            }
        ]
    }
    with pytest.raises(ValidationError):
        ExtractedMetricBatch.model_validate(payload)


def test_semantic_contract_exporta_json_schema():
    schema = get_semantic_contract_json_schema()
    batch_schema = get_semantic_batch_contract_json_schema()

    assert schema["properties"]["metrics"]
    assert batch_schema["properties"]["documents"]
