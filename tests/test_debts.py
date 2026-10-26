from decimal import Decimal

import pytest

DIVIDA_BASE = {"creditor": "Banco Exemplo", "original_amount": "1500.50"}


def test_cria_divida_completa(client, ana):
    payload = {
        "creditor": "Banco Exemplo",
        "description": "Empréstimo pessoal",
        "original_amount": "1500.50",
        "monthly_interest_rate": "2.5",
        "installment_amount": "250.00",
        "installment_count": 6,
        "due_date": "2026-12-10",
    }

    resposta = client.post("/debts/", json=payload, headers=ana)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["creditor"] == "Banco Exemplo"
    assert Decimal(corpo["original_amount"]) == Decimal("1500.50")
    assert Decimal(corpo["monthly_interest_rate"]) == Decimal("2.5")
    assert corpo["installment_count"] == 6
    assert corpo["due_date"] == "2026-12-10"
    assert corpo["status"] == "ativa"


def test_cria_divida_informal_sem_juros_parcelas_nem_vencimento(client, ana):
    resposta = client.post("/debts/", json=DIVIDA_BASE, headers=ana)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["monthly_interest_rate"] is None
    assert corpo["installment_amount"] is None
    assert corpo["installment_count"] is None
    assert corpo["due_date"] is None
    assert corpo["status"] == "ativa"


def test_cliente_nao_define_user_id_nem_status(client, ana):
    meu_id = client.get("/users/me", headers=ana).json()["id"]
    payload = {**DIVIDA_BASE, "user_id": 999, "status": "quitada"}

    resposta = client.post("/debts/", json=payload, headers=ana)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["user_id"] == meu_id
    assert corpo["status"] == "ativa"


@pytest.mark.parametrize(
    "alteracao",
    [
        pytest.param({"original_amount": "0"}, id="valor_zero"),
        pytest.param({"original_amount": "-100"}, id="valor_negativo"),
        pytest.param({"original_amount": "10.123"}, id="tres_casas_decimais"),
        pytest.param({"creditor": "   "}, id="credor_so_espacos"),
        pytest.param({"monthly_interest_rate": "-1"}, id="juros_negativo"),
        pytest.param({"installment_amount": "100.00"}, id="parcela_sem_quantidade"),
        pytest.param({"installment_count": 6}, id="quantidade_sem_parcela"),
        pytest.param(
            {"installment_amount": "100.00", "installment_count": 0}, id="quantidade_zero"
        ),
    ],
)
def test_rejeita_dados_invalidos(client, ana, alteracao):
    payload = {**DIVIDA_BASE, **alteracao}

    resposta = client.post("/debts/", json=payload, headers=ana)

    assert resposta.status_code == 422, resposta.text


def test_rotas_exigem_autenticacao(client):
    assert client.post("/debts/", json=DIVIDA_BASE).status_code == 401
    assert client.get("/debts/").status_code == 401


def test_usuario_so_ve_as_proprias_dividas(client, ana, bruno):
    criada = client.post("/debts/", json=DIVIDA_BASE, headers=ana)
    assert criada.status_code == 200, criada.text

    lista_ana = client.get("/debts/", headers=ana).json()
    lista_bruno = client.get("/debts/", headers=bruno).json()

    assert len(lista_ana) == 1
    assert lista_ana[0]["creditor"] == "Banco Exemplo"
    assert lista_bruno == []