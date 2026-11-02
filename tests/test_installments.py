from datetime import date, timedelta
from decimal import Decimal

import pytest

HOJE = date.today()
# Bem no futuro: assim todas as parcelas ficam pendentes, e o teste não envelhece.
PRIMEIRO_VENCIMENTO = "2099-01-31"


def payload_parcelado(**extra):
    return {
        "creditor": "Banco Exemplo",
        "original_amount": "1200.00",
        "installment_count": 3,
        "installment_amount": "400.00",
        "due_date": PRIMEIRO_VENCIMENTO,
        **extra,
    }


def payload_previa(**extra):
    return {
        "original_amount": "1000.00",
        "installment_count": 3,
        "first_due_date": PRIMEIRO_VENCIMENTO,
        **extra,
    }


def cadastrar(client, headers, payload):
    resposta = client.post("/debts/", json=payload, headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def parcelas_da(client, headers, debt_id):
    resposta = client.get(f"/debts/{debt_id}/installments", headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def pagar(client, headers, debt_id, amount, **extra):
    return client.post(
        f"/debts/{debt_id}/payments", json={"amount": amount, **extra}, headers=headers
    )


def previa(client, headers, payload):
    return client.post("/debts/installments-preview", json=payload, headers=headers)


def test_cadastro_parcelado_cria_parcelas_mensais(client, ana):
    divida = cadastrar(client, ana, payload_parcelado())

    parcelas = parcelas_da(client, ana, divida["id"])

    assert [p["number"] for p in parcelas] == [1, 2, 3]
    assert [p["due_date"] for p in parcelas] == ["2099-01-31", "2099-02-28", "2099-03-31"]
    assert all(Decimal(p["amount"]) == Decimal("400.00") for p in parcelas)
    assert all(Decimal(p["paid_amount"]) == Decimal("0") for p in parcelas)
    assert all(p["status"] == "pendente" for p in parcelas)
    assert all(p["days_overdue"] == 0 for p in parcelas)


def test_valor_da_parcela_e_estimado_quando_nao_informado(client, ana):
    payload = payload_parcelado(original_amount="1000.00")
    payload.pop("installment_amount")

    divida = cadastrar(client, ana, payload)
    parcelas = parcelas_da(client, ana, divida["id"])

    assert Decimal(divida["installment_amount"]) == Decimal("333.33")
    assert all(Decimal(p["amount"]) == Decimal("333.33") for p in parcelas)


def test_valor_informado_prevalece_sobre_a_divisao(client, ana):
    # Com juros, a soma das parcelas passa do valor total: o valor do contrato é que vale.
    divida = cadastrar(client, ana, payload_parcelado(installment_amount="450.00"))

    parcelas = parcelas_da(client, ana, divida["id"])

    assert all(Decimal(p["amount"]) == Decimal("450.00") for p in parcelas)


@pytest.mark.parametrize(
    "alteracao",
    [
        pytest.param({"due_date": None}, id="quantidade_sem_vencimento"),
        pytest.param({"installment_count": None}, id="valor_da_parcela_sem_quantidade"),
        pytest.param({"installment_count": 0}, id="quantidade_zero"),
        pytest.param({"installment_count": 481}, id="quantidade_acima_do_limite"),
    ],
)
def test_rejeita_parcelamento_invalido(client, ana, alteracao):
    resposta = client.post("/debts/", json=payload_parcelado(**alteracao), headers=ana)

    assert resposta.status_code == 422, resposta.text


def test_divida_nao_e_salva_quando_nao_da_para_dividir(client, ana):
    payload = payload_parcelado(original_amount="0.01")
    payload.pop("installment_amount")

    resposta = client.post("/debts/", json=payload, headers=ana)

    assert resposta.status_code == 422, resposta.text
    assert client.get("/debts/", headers=ana).json() == []


def test_divida_sem_parcelas_nao_tem_cronograma(client, ana, divida_da_ana):
    assert parcelas_da(client, ana, divida_da_ana["id"]) == []


def test_parcelas_vencidas_e_pendentes_pela_data_de_hoje(client, ana):
    primeira = (HOJE - timedelta(days=20)).isoformat()
    divida = cadastrar(client, ana, payload_parcelado(due_date=primeira))

    parcelas = parcelas_da(client, ana, divida["id"])

    assert [p["status"] for p in parcelas] == ["vencida", "pendente", "pendente"]
    assert [p["days_overdue"] for p in parcelas] == [20, 0, 0]


def test_pagamento_ligado_a_parcela_quita_so_essa_parcela(client, ana):
    divida = cadastrar(client, ana, payload_parcelado())
    primeira = parcelas_da(client, ana, divida["id"])[0]

    resposta = pagar(client, ana, divida["id"], "400.00", installment_id=primeira["id"])

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["installment_id"] == primeira["id"]
    parcelas = parcelas_da(client, ana, divida["id"])
    assert [p["status"] for p in parcelas] == ["paga", "pendente", "pendente"]
    assert Decimal(parcelas[0]["paid_amount"]) == Decimal("400.00")


def test_pagamento_parcial_e_depois_completo(client, ana):
    divida = cadastrar(client, ana, payload_parcelado())
    primeira = parcelas_da(client, ana, divida["id"])[0]

    pagar(client, ana, divida["id"], "150.00", installment_id=primeira["id"])
    assert parcelas_da(client, ana, divida["id"])[0]["status"] == "parcial"

    pagar(client, ana, divida["id"], "250.00", installment_id=primeira["id"])
    parcela = parcelas_da(client, ana, divida["id"])[0]

    assert parcela["status"] == "paga"
    assert Decimal(parcela["paid_amount"]) == Decimal("400.00")


def test_excedente_nao_passa_para_a_proxima_parcela(client, ana):
    divida = cadastrar(client, ana, payload_parcelado())
    primeira = parcelas_da(client, ana, divida["id"])[0]

    pagar(client, ana, divida["id"], "500.00", installment_id=primeira["id"])

    parcelas = parcelas_da(client, ana, divida["id"])
    assert [p["status"] for p in parcelas] == ["paga", "pendente", "pendente"]
    assert Decimal(parcelas[0]["paid_amount"]) == Decimal("500.00")
    assert Decimal(parcelas[1]["paid_amount"]) == Decimal("0")
    # O histórico guarda o valor realmente pago.
    pagamentos = client.get(f"/debts/{divida['id']}/payments", headers=ana).json()
    assert Decimal(pagamentos[0]["amount"]) == Decimal("500.00")


def test_pagamento_sem_parcela_conta_no_total_mas_nao_quita_parcela(client, ana):
    divida = cadastrar(client, ana, payload_parcelado())

    pagar(client, ana, divida["id"], "400.00")

    detalhe = client.get(f"/debts/{divida['id']}", headers=ana).json()
    assert Decimal(detalhe["total_paid"]) == Decimal("400.00")
    assert all(p["status"] == "pendente" for p in parcelas_da(client, ana, divida["id"]))


def test_pagamento_com_parcela_de_outra_divida_retorna_404(client, ana):
    divida_a = cadastrar(client, ana, payload_parcelado(creditor="Credor A"))
    divida_b = cadastrar(client, ana, payload_parcelado(creditor="Credor B"))
    parcela_b = parcelas_da(client, ana, divida_b["id"])[0]

    resposta = pagar(client, ana, divida_a["id"], "100.00", installment_id=parcela_b["id"])

    assert resposta.status_code == 404, resposta.text
    assert client.get(f"/debts/{divida_a['id']}/payments", headers=ana).json() == []


def test_pagamento_com_parcela_inexistente_retorna_404(client, ana):
    divida = cadastrar(client, ana, payload_parcelado())

    resposta = pagar(client, ana, divida["id"], "100.00", installment_id=99999)

    assert resposta.status_code == 404, resposta.text


def test_quitar_encerra_parcelas_sem_pagamento_e_reabrir_desfaz(client, ana):
    divida = cadastrar(client, ana, payload_parcelado())
    primeira = parcelas_da(client, ana, divida["id"])[0]
    pagar(client, ana, divida["id"], "400.00", installment_id=primeira["id"])

    assert client.post(f"/debts/{divida['id']}/settle", json={}, headers=ana).status_code == 200
    assert [p["status"] for p in parcelas_da(client, ana, divida["id"])] == [
        "paga", "encerrada", "encerrada",
    ]

    assert client.post(f"/debts/{divida['id']}/reopen", headers=ana).status_code == 200
    assert [p["status"] for p in parcelas_da(client, ana, divida["id"])] == [
        "paga", "pendente", "pendente",
    ]


def test_previa_mostra_o_cronograma_e_nao_grava_nada(client, ana):
    resposta = previa(client, ana, payload_previa())

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert [p["number"] for p in corpo["installments"]] == [1, 2, 3]
    assert [p["due_date"] for p in corpo["installments"]] == [
        "2099-01-31", "2099-02-28", "2099-03-31",
    ]
    assert client.get("/debts/", headers=ana).json() == []


def test_previa_com_valor_informado(client, ana):
    corpo = previa(
        client, ana, payload_previa(original_amount="1200.00", installment_amount="450.00")
    ).json()

    assert corpo["amount_is_estimated"] is False
    assert Decimal(corpo["installment_amount"]) == Decimal("450.00")
    assert Decimal(corpo["total_of_installments"]) == Decimal("1350.00")
    assert "editar" in corpo["notices"][0]
    assert any("soma das parcelas" in aviso for aviso in corpo["notices"])
    assert not any("estimativa" in aviso for aviso in corpo["notices"])


def test_previa_estima_o_valor_quando_nao_informado(client, ana):
    corpo = previa(client, ana, payload_previa()).json()  # 1000 dividido por 3

    assert corpo["amount_is_estimated"] is True
    assert Decimal(corpo["installment_amount"]) == Decimal("333.33")
    assert Decimal(corpo["total_of_installments"]) == Decimal("999.99")
    assert any("estimativa" in aviso for aviso in corpo["notices"])
    assert any("soma das parcelas" in aviso for aviso in corpo["notices"])


def test_previa_sem_aviso_de_soma_quando_ela_bate(client, ana):
    corpo = previa(client, ana, payload_previa(original_amount="1200.00")).json()  # 400 x 3

    assert Decimal(corpo["total_of_installments"]) == Decimal("1200.00")
    assert not any("soma das parcelas" in aviso for aviso in corpo["notices"])


def test_previa_e_igual_ao_cronograma_salvo(client, ana):
    mostrada = previa(client, ana, payload_previa()).json()

    divida = cadastrar(
        client,
        ana,
        {
            "creditor": "Banco Exemplo",
            "original_amount": "1000.00",
            "installment_count": 3,
            "due_date": PRIMEIRO_VENCIMENTO,
        },
    )
    salvas = parcelas_da(client, ana, divida["id"])

    esperado = [(p["number"], p["due_date"], Decimal(p["amount"])) for p in mostrada["installments"]]
    obtido = [(p["number"], p["due_date"], Decimal(p["amount"])) for p in salvas]
    assert obtido == esperado


@pytest.mark.parametrize(
    "alteracao",
    [
        pytest.param({"installment_count": 0}, id="quantidade_zero"),
        pytest.param({"installment_count": 481}, id="quantidade_acima_do_limite"),
        pytest.param({"original_amount": "0"}, id="valor_total_zero"),
        pytest.param({"first_due_date": None}, id="sem_primeiro_vencimento"),
        pytest.param({"installment_amount": "0"}, id="valor_da_parcela_zero"),
        pytest.param({"original_amount": "0.01"}, id="valor_pequeno_demais_para_dividir"),
    ],
)
def test_previa_rejeita_dados_invalidos(client, ana, alteracao):
    resposta = previa(client, ana, payload_previa(**alteracao))

    assert resposta.status_code == 422, resposta.text


def test_rotas_de_parcelas_exigem_autenticacao(client, divida_da_ana):
    assert client.post("/debts/installments-preview", json=payload_previa()).status_code == 401
    assert client.get(f"/debts/{divida_da_ana['id']}/installments").status_code == 401


def test_usuario_nao_ve_parcelas_de_divida_de_outro(client, ana, bruno):
    divida = cadastrar(client, ana, payload_parcelado())

    assert client.get(f"/debts/{divida['id']}/installments", headers=bruno).status_code == 404
    assert client.get("/debts/99999/installments", headers=ana).status_code == 404


def test_usuario_nao_liga_pagamento_a_parcela_de_outro(client, ana, bruno):
    divida_ana = cadastrar(client, ana, payload_parcelado())
    parcela_ana = parcelas_da(client, ana, divida_ana["id"])[0]
    divida_bruno = cadastrar(client, bruno, payload_parcelado())

    resposta = pagar(client, bruno, divida_bruno["id"], "100.00", installment_id=parcela_ana["id"])

    assert resposta.status_code == 404, resposta.text
    parcela_depois = parcelas_da(client, ana, divida_ana["id"])[0]
    assert parcela_depois["status"] == "pendente"
    assert Decimal(parcela_depois["paid_amount"]) == Decimal("0")