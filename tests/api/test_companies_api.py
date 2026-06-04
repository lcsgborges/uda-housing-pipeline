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


def test_atualiza_busca_e_remove_empresa(client):
    created = client.post(
        "/api/companies",
        json={
            "name": "Tenda",
            "ticker": "TEND3",
            "ri_url": "https://ri.tenda.com",
            "is_active": True,
        },
    ).json()

    detail = client.get(f"/api/companies/{created['id']}")
    updated = client.put(
        f"/api/companies/{created['id']}",
        json={"name": "Construtora Tenda", "is_active": False},
    )
    deleted = client.delete(f"/api/companies/{created['id']}")
    missing = client.get(f"/api/companies/{created['id']}")

    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["name"] == "Construtora Tenda"
    assert updated.json()["is_active"] is False
    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_cria_empresa_duplicada_retorna_409(client):
    payload = {
        "name": "Cury",
        "ticker": "CURY3",
        "ri_url": "https://ri.cury.com.br",
        "is_active": True,
    }
    first = client.post("/api/companies", json=payload)
    duplicate = client.post("/api/companies", json=payload)

    assert first.status_code == 201
    assert duplicate.status_code == 409
