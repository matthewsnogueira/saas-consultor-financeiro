from app.core.database import engine


def test_usa_banco_de_teste():
    assert engine.url.database == "saas_financeiro_test"


def test_api_responde(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"mensagem": "API do SaaS financeiro está no ar"}