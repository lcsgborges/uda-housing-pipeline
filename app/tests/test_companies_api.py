def test_cria_empresa(client):
    payload = {
        "name": "MRV",
        "ticker": "MRVE3",
        "ri_url": "https://ri.mrv.com.br",
        "is_active": True,
    }
    response = client.post("/api/companies", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "MRV"


def test_lista_empresas(client):
    payload = {
        "name": "Direcional",
        "ticker": "DIRR3",
        "ri_url": "https://ri.direcional.com.br",
        "is_active": True,
    }
    client.post("/api/companies", json=payload)
    response = client.get("/api/companies")
    assert response.status_code == 200
    assert len(response.json()) == 1
