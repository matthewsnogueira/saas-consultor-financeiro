from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.schemas.debt import DelayState, InstallmentStatus
from app.services.debt_service import compute_debt_delay

HOJE = date(2026, 10, 30)


@pytest.fixture(autouse=True)
def clean_database():
    """Sobrescreve a fixture do conftest: estes testes não usam banco, então ficam rápidos."""
    yield


def dias(n):
    return timedelta(days=n)


def parcela(numero, vencimento, status, valor="100.00", pago="0", atraso=0):
    return {
        "number": numero,
        "due_date": vencimento,
        "amount": Decimal(valor),
        "paid_amount": Decimal(pago),
        "status": status,
        "days_overdue": atraso,
    }


def calcular(settled=False, due_date=None, original="1000.00", pago="0", parcelas=None):
    return compute_debt_delay(
        debt_is_settled=settled,
        due_date=due_date,
        original_amount=Decimal(original),
        total_paid=Decimal(pago),
        installments=parcelas or [],
        today=HOJE,
    )


def test_divida_quitada_nao_tem_atraso():
    parcelas = [parcela(1, HOJE - dias(30), InstallmentStatus.encerrada)]

    r = calcular(settled=True, parcelas=parcelas)

    assert r["state"] == DelayState.quitada
    assert r["days_overdue"] == 0
    assert r["overdue_installments"] is None
    assert "quitada" in r["notice"]


def test_sem_vencimento_responde_sem_vencimento_definido():
    r = calcular()

    assert r["state"] == DelayState.sem_vencimento_definido
    assert r["state"] != DelayState.em_dia
    assert r["overdue_amount"] is None
    assert "vencimento" in r["notice"]


def test_sem_vencimento_continua_sem_vencimento_mesmo_com_total_pago():
    r = calcular(pago="1000.00")

    assert r["state"] == DelayState.sem_vencimento_definido


def test_sem_parcelas_vencimento_passado_fica_em_atraso_com_valor_estimado():
    r = calcular(due_date=HOJE - dias(10), pago="300.00")

    assert r["state"] == DelayState.em_atraso
    assert r["days_overdue"] == 10
    assert r["overdue_amount"] == Decimal("700.00")
    assert r["overdue_amount_is_estimated"] is True
    assert r["overdue_installments"] is None
    assert "estimativa" in r["notice"]


def test_sem_parcelas_que_vence_hoje_ainda_esta_em_dia():
    r = calcular(due_date=HOJE)

    assert r["state"] == DelayState.em_dia
    assert r["days_overdue"] == 0
    assert r["next_due_date"] == HOJE


def test_sem_parcelas_com_vencimento_futuro_esta_em_dia():
    r = calcular(due_date=HOJE + dias(5))

    assert r["state"] == DelayState.em_dia
    assert r["next_due_date"] == HOJE + dias(5)


def test_sem_parcelas_vencida_mas_totalmente_paga_nao_esta_em_atraso():
    r = calcular(due_date=HOJE - dias(10), pago="1000.00")

    assert r["state"] == DelayState.em_dia
    assert r["overdue_amount"] is None
    assert "quitação" in r["notice"]


def test_parcela_vencida_coloca_a_divida_em_atraso():
    parcelas = [
        parcela(1, HOJE - dias(30), InstallmentStatus.vencida, atraso=30),
        parcela(2, HOJE + dias(1), InstallmentStatus.pendente),
        parcela(3, HOJE + dias(31), InstallmentStatus.pendente),
    ]

    r = calcular(due_date=HOJE - dias(30), parcelas=parcelas)

    assert r["state"] == DelayState.em_atraso
    assert r["days_overdue"] == 30
    assert r["overdue_installments"] == 1
    assert r["overdue_amount"] == Decimal("100.00")
    assert r["overdue_amount_is_estimated"] is False
    assert r["next_due_date"] == HOJE + dias(1)
    assert "1 parcela" in r["notice"]


def test_varias_parcelas_vencidas_somam_so_o_que_falta():
    parcelas = [
        parcela(1, HOJE - dias(40), InstallmentStatus.vencida, atraso=40),
        parcela(2, HOJE - dias(10), InstallmentStatus.vencida, pago="30.00", atraso=10),
    ]

    r = calcular(parcelas=parcelas)

    assert r["overdue_installments"] == 2
    assert r["overdue_amount"] == Decimal("170.00")
    assert r["days_overdue"] == 40
    assert "R$ 170,00" in r["notice"]


def test_sem_parcelas_vencidas_a_divida_esta_em_dia():
    parcelas = [
        parcela(1, HOJE + dias(10), InstallmentStatus.pendente),
        parcela(2, HOJE + dias(40), InstallmentStatus.pendente),
    ]

    r = calcular(parcelas=parcelas)

    assert r["state"] == DelayState.em_dia
    assert r["overdue_installments"] == 0
    assert r["overdue_amount"] == Decimal("0")
    assert r["next_due_date"] == HOJE + dias(10)
    assert r["notice"] == "Nenhuma parcela vencida."


def test_todas_as_parcelas_pagas_nao_confirma_a_quitacao():
    parcelas = [
        parcela(1, HOJE - dias(30), InstallmentStatus.paga, pago="100.00"),
        parcela(2, HOJE - dias(1), InstallmentStatus.paga, pago="100.00"),
    ]

    r = calcular(parcelas=parcelas)

    assert r["state"] == DelayState.em_dia
    assert r["next_due_date"] is None
    assert "quitação" in r["notice"]


def test_proximo_vencimento_ignora_parcelas_pagas():
    parcelas = [
        parcela(1, HOJE - dias(30), InstallmentStatus.paga, pago="100.00"),
        parcela(2, HOJE + dias(5), InstallmentStatus.pendente),
    ]

    r = calcular(parcelas=parcelas)

    assert r["next_due_date"] == HOJE + dias(5)


def test_parcela_parcial_dentro_do_prazo_conta_como_proximo_vencimento():
    parcelas = [parcela(1, HOJE + dias(3), InstallmentStatus.parcial, pago="40.00")]

    r = calcular(parcelas=parcelas)

    assert r["state"] == DelayState.em_dia
    assert r["next_due_date"] == HOJE + dias(3)


def test_parcelas_prevalecem_sobre_o_vencimento_da_divida():
    parcelas = [parcela(1, HOJE + dias(10), InstallmentStatus.pendente)]

    r = calcular(due_date=HOJE - dias(50), parcelas=parcelas)

    assert r["state"] == DelayState.em_dia