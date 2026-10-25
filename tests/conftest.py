import os

# IMPORTANTE: isto precisa vir ANTES de qualquer import de "app".
# O database.py monta o engine ao ser importado, lendo DB_NAME do ambiente.
os.environ["DB_NAME"] = "saas_financeiro_test"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app

# Importa os modelos para o Base.metadata conhecer todas as tabelas.
from app.models import user, income, expense, debt  # noqa: F401

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