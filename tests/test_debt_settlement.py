from datetime import date, timedelta
from decimal import Decimal

HOJE = date.today()


def pagar(client, headers, debt_id, amount, **extra):
    return client.post(
        f"/debts/{debt_id}/payments", json={"amount": amount, **extra}, headers=headers
    )


def informar_saldo(client, headers, debt_id, amount, **extra):
    return client.post(
        f"/debts/{debt_id}/reported-balance", json={"amount": amount, **extra}, headers=headers
    )


def quitar(client, headers, debt_id, **corpo):
    return client.post(f"/debts/{debt_id}/settle", json=corpo, headers=headers)


def reabrir(client, headers, debt_id):
    return client.post(f"/debts/{debt_id}/reopen", headers=headers)


def detalhe(client, headers, debt_id):
    resposta = client.get(f"/debts/{debt_id}", headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_quita_com_corpo_vazio_usa_hoje_e_fica_como_declarada(client, ana, divida_da_ana):
    resposta = quitar(client, ana, divida_da_ana["id"])

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "quitada"
    assert corpo["settled_at"] == HOJE.isoformat()
    assert corpo["creditor_confirmed"] is False


def test_quita_com_confirmacao_do_credor_e_data_passada(client, ana, divida_da_ana):
    data = (HOJE - timedelta(days=3)).isoformat()

    resposta = quitar(client, ana, divida_da_ana["id"], settled_at=data, creditor_confirmed=True)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "quitada"
    assert corpo["settled_at"] == data
    assert corpo["creditor_confirmed"] is True


def test_rejeita_data_de_quitacao_futura(client, ana, divida_da_ana):
    futura = (HOJE + timedelta(days=1)).isoformat()

    resposta = quitar(client, ana, divida_da_ana["id"], settled_at=futura)

    assert resposta.status_code == 422, resposta.text
    assert detalhe(client, ana, divida_da_ana["id"])["status"] == "ativa"


def test_quitar_duas_vezes_retorna_409(client, ana, divida_da_ana):
    assert quitar(client, ana, divida_da_ana["id"]).status_code == 200

    resposta = quitar(client, ana, divida_da_ana["id"])

    assert resposta.status_code == 409, resposta.text


def test_quitacao_preserva_pagamentos_e_zera_saldo_estimado(client, ana, divida_da_ana):
    # Pagou menos que o valor original (por exemplo, um desconto negociado).
    pagar(client, ana, divida_da_ana["id"], "300.00")

    quitar(client, ana, divida_da_ana["id"])
    corpo = detalhe(client, ana, divida_da_ana["id"])
    pagamentos = client.get(f"/debts/{divida_da_ana['id']}/payments", headers=ana).json()

    assert corpo["status"] == "quitada"
    assert Decimal(corpo["total_paid"]) == Decimal("300.00")
    assert Decimal(corpo["estimated_balance"]) == Decimal("0")
    assert "quitada" in corpo["estimate_notice"]
    assert HOJE.strftime("%d/%m/%Y") in corpo["estimate_notice"]
    assert len(pagamentos) == 1


def test_aviso_menciona_confirmacao_do_credor(client, ana, divida_da_ana):
    quitar(client, ana, divida_da_ana["id"], creditor_confirmed=True)

    corpo = detalhe(client, ana, divida_da_ana["id"])

    assert "confirmação do credor" in corpo["estimate_notice"]


def test_saldo_informado_e_preservado_ao_quitar(client, ana, divida_da_ana):
    informar_saldo(client, ana, divida_da_ana["id"], "700.00")

    quitar(client, ana, divida_da_ana["id"])
    corpo = detalhe(client, ana, divida_da_ana["id"])

    assert Decimal(corpo["reported_balance"]["amount"]) == Decimal("700.00")


def test_aceita_pagamento_em_divida_quitada(client, ana, divida_da_ana):
    quitar(client, ana, divida_da_ana["id"])

    resposta = pagar(client, ana, divida_da_ana["id"], "50.00")

    assert resposta.status_code == 200, resposta.text
    corpo = detalhe(client, ana, divida_da_ana["id"])
    assert corpo["status"] == "quitada"
    assert Decimal(corpo["total_paid"]) == Decimal("50.00")


def test_reabrir_volta_a_ativa_e_limpa_os_campos_da_quitacao(client, ana, divida_da_ana):
    pagar(client, ana, divida_da_ana["id"], "300.00")
    quitar(client, ana, divida_da_ana["id"], creditor_confirmed=True)

    resposta = reabrir(client, ana, divida_da_ana["id"])

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "ativa"
    assert corpo["settled_at"] is None
    assert corpo["creditor_confirmed"] is False

    detalhe_atual = detalhe(client, ana, divida_da_ana["id"])
    assert Decimal(detalhe_atual["total_paid"]) == Decimal("300.00")
    assert Decimal(detalhe_atual["estimated_balance"]) == Decimal("700.00")


def test_reabrir_divida_ativa_retorna_409(client, ana, divida_da_ana):
    resposta = reabrir(client, ana, divida_da_ana["id"])

    assert resposta.status_code == 409, resposta.text


def test_rotas_de_quitacao_exigem_autenticacao(client, divida_da_ana):
    id_ = divida_da_ana["id"]

    assert client.post(f"/debts/{id_}/settle", json={}).status_code == 401
    assert client.post(f"/debts/{id_}/reopen").status_code == 401


def test_usuario_nao_quita_nem_reabre_divida_de_outro(client, ana, bruno, divida_da_ana):
    id_ = divida_da_ana["id"]

    assert quitar(client, bruno, id_).status_code == 404
    assert detalhe(client, ana, id_)["status"] == "ativa"

    quitar(client, ana, id_)
    assert reabrir(client, bruno, id_).status_code == 404
    assert detalhe(client, ana, id_)["status"] == "quitada"


def test_quitar_e_reabrir_divida_inexistente_retorna_404(client, ana):
    assert quitar(client, ana, 99999).status_code == 404
    assert reabrir(client, ana, 99999).status_code == 404