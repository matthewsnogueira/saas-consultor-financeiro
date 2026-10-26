import os

# IMPORTANTE: isto precisa vir ANTES de qualquer import de "app".
# O database.py monta o engine ao ser importado, lendo DB_NAME do ambiente.
os.environ["DB_NAME"] = "saas_financeiro_test"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app

# Importa os modelos para o Base.metadata conhecer todas as tabelas.
from app.models import user, income, expense, debt, debt_payment, debt_reported_balance  # noqa: F401

# Proteção: nunca rodar testes em um banco que não seja de teste.
assert engine.url.database.endswith("_test"), (
    f"Testes abortados: o banco em uso é '{engine.url.database}', não um banco de teste."
)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)

SENHA_TESTE = "senha-de-teste-123"


def criar_usuario_e_logar(client, name, email):
    """Cadastra um usuário fictício, faz login e devolve o cabeçalho de autenticação."""
    resposta = client.post("/users/", json={"name": name, "email": email, "password": SENHA_TESTE})
    assert resposta.status_code in (200, 201), resposta.text

    resposta = client.post("/users/login", json={"email": email, "password": SENHA_TESTE})
    assert resposta.status_code == 200, resposta.text

    token = resposta.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def ana(client):
    return criar_usuario_e_logar(client, "Ana Teste", "ana@exemplo.com")


@pytest.fixture
def bruno(client):
    return criar_usuario_e_logar(client, "Bruno Teste", "bruno@exemplo.com")


@pytest.fixture
def divida_da_ana(client, ana):
    resposta = client.post(
        "/debts/",
        json={"creditor": "Banco Exemplo", "original_amount": "1000.00"},
        headers=ana,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()   