import json
from pathlib import Path


def test_fixture_conjuntura_3t2025_transcreve_exemplo():
    fixture_path = Path("docs/exemplos/conjuntura_3t2025_exemplo.json")
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert data["period_year"] == 2025
    assert data["period_quarter"] == 3
    assert data["unit"] == "%"

    lancamentos = data["tables"][0]
    vendas = data["tables"][1]

    assert lancamentos["metric_group"] == "lancamentos"
    assert lancamentos["totals"]["x_2t25"] == 14
    assert lancamentos["rows"][0]["company"] == "MRV"
    assert lancamentos["rows"][0]["x_2t25"] == -32

    assert vendas["metric_group"] == "vendas"
    assert vendas["totals"]["x_3t24"] == -5
    assert vendas["rows"][3]["company"] == "Plano & Plano"
    assert vendas["rows"][3]["x_3t24"] == -36
