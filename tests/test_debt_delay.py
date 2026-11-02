from datetime import date, timedelta
from decimal import Decimal

HOJE = date.today()


def cadastrar(client, headers, payload):
    resposta = client.post("/debts/", json=payload, headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def divida_parcelada_vencendo(client, headers, dias_atras=20):
    return cadastrar(
        client,
        headers,
        {
            "creditor": "Banco Exemplo",
            "original_amount": "1200.00",
            "installment_count": 3,
            "installment_amount": "400.00",
            "due_date": (HOJE - timedelta(days=dias_atras)).isoformat(),
        },
    )


def atraso_da(client, headers, debt_id):
    resposta = client.get(f"/debts/{debt_id}", headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["delay"]


def parcelas_da(client, headers, debt_id):
    return client.get(f"/debts/{debt_id}/installments", headers=headers).json()


def test_divida_sem_vencimento_responde_sem_vencimento_definido(client, ana, divida_da_ana):
    delay = atraso_da(client, ana, divida_da_ana["id"])

    assert delay["state"] == "sem_vencimento_definido"
    assert delay["overdue_amount"] is None


def test_parcela_vencida_aparece_no_detalhe_da_divida(client, ana):
    divida = divida_parcelada_vencendo(client, ana, dias_atras=20)

    delay = atraso_da(client, ana, divida["id"])

    assert delay["state"] == "em_atraso"
    assert delay["overdue_installments"] == 1
    assert Decimal(delay["overdue_amount"]) == Decimal("400.00")
    assert delay["days_overdue"] == 20
    assert delay["overdue_amount_is_estimated"] is False
    assert delay["next_due_date"] is not None


def test_pagar_a_parcela_vencida_tira_a_divida_do_atraso(client, ana):
    divida = divida_parcelada_vencendo(client, ana)
    primeira = parcelas_da(client, ana, divida["id"])[0]

    client.post(
        f"/debts/{divida['id']}/payments",
        json={"amount": "400.00", "installment_id": primeira["id"]},
        headers=ana,
    )
    delay = atraso_da(client, ana, divida["id"])

    assert delay["state"] == "em_dia"
    assert delay["overdue_installments"] == 0


def test_pagamento_sem_indicar_a_parcela_nao_tira_do_atraso(client, ana):
    divida = divida_parcelada_vencendo(client, ana)

    client.post(f"/debts/{divida['id']}/payments", json={"amount": "400.00"}, headers=ana)
    delay = atraso_da(client, ana, divida["id"])

    assert delay["state"] == "em_atraso"
    assert "sem indicar a parcela" in delay["notice"]


def test_quitar_a_divida_zera_o_atraso(client, ana):
    divida = divida_parcelada_vencendo(client, ana)

    client.post(f"/debts/{divida['id']}/settle", json={}, headers=ana)
    delay = atraso_da(client, ana, divida["id"])

    assert delay["state"] == "quitada"
    assert delay["days_overdue"] == 0


def test_divida_informal_vencida_tem_atraso_estimado_ate_ser_paga(client, ana):
    divida = cadastrar(
        client,
        ana,
        {
            "creditor": "Amigo",
            "original_amount": "1000.00",
            "due_date": (HOJE - timedelta(days=10)).isoformat(),
        },
    )

    delay = atraso_da(client, ana, divida["id"])
    assert delay["state"] == "em_atraso"
    assert delay["days_overdue"] == 10
    assert Decimal(delay["overdue_amount"]) == Decimal("1000.00")
    assert delay["overdue_amount_is_estimated"] is True

    client.post(f"/debts/{divida['id']}/payments", json={"amount": "1000.00"}, headers=ana)
    assert atraso_da(client, ana, divida["id"])["state"] == "em_dia"