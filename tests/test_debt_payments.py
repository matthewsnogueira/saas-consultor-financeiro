from datetime import date, timedelta
from decimal import Decimal

import pytest

HOJE = date.today()


def pagar(client, headers, debt_id, amount, **extra):
    return client.post(
        f"/debts/{debt_id}/payments", json={"amount": amount, **extra}, headers=headers
    )


def informar_saldo(client, headers, debt_id, amount, **extra):
    return client.post(
        f"/debts/{debt_id}/reported-balance", json={"amount": amount, **extra}, headers=headers
    )


def detalhe(client, headers, debt_id):
    resposta = client.get(f"/debts/{debt_id}", headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_registra_pagamento(client, ana, divida_da_ana):
    resposta = pagar(
        client, ana, divida_da_ana["id"], "300.00",
        payment_date=(HOJE - timedelta(days=5)).isoformat(), notes="Primeira parcela",
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["debt_id"] == divida_da_ana["id"]
    assert Decimal(corpo["amount"]) == Decimal("300.00")
    assert corpo["payment_date"] == (HOJE - timedelta(days=5)).isoformat()
    assert corpo["notes"] == "Primeira parcela"


def test_pagamento_sem_data_usa_hoje(client, ana, divida_da_ana):
    resposta = pagar(client, ana, divida_da_ana["id"], "50.00")

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["payment_date"] == HOJE.isoformat()


@pytest.mark.parametrize(
    "alteracao",
    [
        pytest.param({"amount": "0"}, id="valor_zero"),
        pytest.param({"amount": "-10"}, id="valor_negativo"),
        pytest.param({"amount": "10.123"}, id="tres_casas_decimais"),
        pytest.param({"payment_date": (HOJE + timedelta(days=1)).isoformat()}, id="data_futura"),
    ],
)
def test_rejeita_pagamento_invalido(client, ana, divida_da_ana, alteracao):
    payload = {"amount": "100.00", **alteracao}

    resposta = client.post(f"/debts/{divida_da_ana['id']}/payments", json=payload, headers=ana)

    assert resposta.status_code == 422, resposta.text


def test_total_pago_e_saldo_estimado(client, ana, divida_da_ana):
    pagar(client, ana, divida_da_ana["id"], "300.00")
    pagar(client, ana, divida_da_ana["id"], "200.00")

    corpo = detalhe(client, ana, divida_da_ana["id"])

    assert Decimal(corpo["total_paid"]) == Decimal("500.00")
    assert Decimal(corpo["estimated_balance"]) == Decimal("500.00")
    assert "estimado" in corpo["estimate_notice"].lower()
    assert corpo["reported_balance"] is None


def test_pagamento_acima_do_valor_original_e_aceito_e_nao_quita(client, ana, divida_da_ana):
    resposta = pagar(client, ana, divida_da_ana["id"], "1200.00")
    assert resposta.status_code == 200, resposta.text

    corpo = detalhe(client, ana, divida_da_ana["id"])

    assert Decimal(corpo["total_paid"]) == Decimal("1200.00")
    assert Decimal(corpo["estimated_balance"]) == Decimal("0")
    assert corpo["status"] == "ativa"
    assert "quitação" in corpo["estimate_notice"]


def test_lista_pagamentos_do_mais_recente_para_o_mais_antigo(client, ana, divida_da_ana):
    pagar(client, ana, divida_da_ana["id"], "100.00", payment_date=(HOJE - timedelta(days=10)).isoformat())
    pagar(client, ana, divida_da_ana["id"], "200.00", payment_date=(HOJE - timedelta(days=2)).isoformat())

    resposta = client.get(f"/debts/{divida_da_ana['id']}/payments", headers=ana)

    assert resposta.status_code == 200, resposta.text
    valores = [Decimal(p["amount"]) for p in resposta.json()]
    assert valores == [Decimal("200.00"), Decimal("100.00")]


def test_pagamentos_de_uma_divida_nao_afetam_outra(client, ana, divida_da_ana):
    outra = client.post(
        "/debts/", json={"creditor": "Outro Credor", "original_amount": "500.00"}, headers=ana
    ).json()

    pagar(client, ana, divida_da_ana["id"], "300.00")

    assert Decimal(detalhe(client, ana, divida_da_ana["id"])["total_paid"]) == Decimal("300.00")
    assert Decimal(detalhe(client, ana, outra["id"])["total_paid"]) == Decimal("0")


def test_saldo_informado_nao_e_alterado_por_novos_pagamentos(client, ana, divida_da_ana):
    resposta = informar_saldo(client, ana, divida_da_ana["id"], "700.00")
    assert resposta.status_code == 200, resposta.text

    pagar(client, ana, divida_da_ana["id"], "100.00")
    corpo = detalhe(client, ana, divida_da_ana["id"])

    assert Decimal(corpo["reported_balance"]["amount"]) == Decimal("700.00")
    assert corpo["reported_balance"]["reference_date"] == HOJE.isoformat()
    assert Decimal(corpo["estimated_balance"]) == Decimal("900.00")


def test_saldo_informado_mais_recente_pela_data_de_referencia_prevalece(client, ana, divida_da_ana):
    informar_saldo(client, ana, divida_da_ana["id"], "600.00", reference_date=HOJE.isoformat())
    # Informado depois, mas se refere a uma data mais antiga: não deve substituir o de hoje.
    informar_saldo(
        client, ana, divida_da_ana["id"], "800.00",
        reference_date=(HOJE - timedelta(days=5)).isoformat(),
    )

    corpo = detalhe(client, ana, divida_da_ana["id"])

    assert Decimal(corpo["reported_balance"]["amount"]) == Decimal("600.00")


@pytest.mark.parametrize(
    "alteracao",
    [
        pytest.param({"amount": "-1"}, id="saldo_negativo"),
        pytest.param({"reference_date": (HOJE + timedelta(days=1)).isoformat()}, id="data_futura"),
    ],
)
def test_rejeita_saldo_informado_invalido(client, ana, divida_da_ana, alteracao):
    payload = {"amount": "100.00", **alteracao}

    resposta = client.post(
        f"/debts/{divida_da_ana['id']}/reported-balance", json=payload, headers=ana
    )

    assert resposta.status_code == 422, resposta.text


def test_aceita_saldo_informado_zero(client, ana, divida_da_ana):
    resposta = informar_saldo(client, ana, divida_da_ana["id"], "0")

    assert resposta.status_code == 200, resposta.text
    assert Decimal(detalhe(client, ana, divida_da_ana["id"])["reported_balance"]["amount"]) == Decimal("0")


def test_rotas_de_pagamento_e_saldo_exigem_autenticacao(client, divida_da_ana):
    id_ = divida_da_ana["id"]

    assert client.get(f"/debts/{id_}").status_code == 401
    assert client.post(f"/debts/{id_}/payments", json={"amount": "10.00"}).status_code == 401
    assert client.get(f"/debts/{id_}/payments").status_code == 401
    assert client.post(f"/debts/{id_}/reported-balance", json={"amount": "10.00"}).status_code == 401


def test_usuario_nao_acessa_divida_de_outro(client, ana, bruno, divida_da_ana):
    id_ = divida_da_ana["id"]

    assert client.get(f"/debts/{id_}", headers=bruno).status_code == 404
    assert pagar(client, bruno, id_, "10.00").status_code == 404
    assert client.get(f"/debts/{id_}/payments", headers=bruno).status_code == 404
    assert informar_saldo(client, bruno, id_, "10.00").status_code == 404

    # Nada do que o Bruno tentou chegou a ser gravado na dívida da Ana.
    corpo = detalhe(client, ana, id_)
    assert Decimal(corpo["total_paid"]) == Decimal("0")
    assert corpo["reported_balance"] is None


def test_divida_inexistente_retorna_404(client, ana):
    assert client.get("/debts/99999", headers=ana).status_code == 404
    assert pagar(client, ana, 99999, "10.00").status_code == 404