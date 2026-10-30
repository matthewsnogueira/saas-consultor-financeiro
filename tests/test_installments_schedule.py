from datetime import date
from decimal import Decimal

import pytest

from app.utils.installments import add_months, build_schedule, estimate_installment_amount


@pytest.fixture(autouse=True)
def clean_database():
    """Sobrescreve a fixture do conftest: estes testes não usam banco, então ficam rápidos."""
    yield


@pytest.mark.parametrize(
    "inicio, meses, esperado",
    [
        pytest.param(date(2026, 1, 15), 0, date(2026, 1, 15), id="zero_meses"),
        pytest.param(date(2026, 1, 15), 1, date(2026, 2, 15), id="mes_comum"),
        pytest.param(date(2026, 1, 31), 1, date(2026, 2, 28), id="31_de_janeiro_vira_28_de_fevereiro"),
        pytest.param(date(2026, 1, 31), 2, date(2026, 3, 31), id="ajuste_nao_se_acumula"),
        pytest.param(date(2028, 1, 31), 1, date(2028, 2, 29), id="ano_bissexto"),
        pytest.param(date(2026, 11, 15), 2, date(2027, 1, 15), id="virada_de_ano"),
        pytest.param(date(2026, 11, 15), 14, date(2028, 1, 15), id="mais_de_um_ano"),
    ],
)
def test_add_months(inicio, meses, esperado):
    assert add_months(inicio, meses) == esperado


def test_cronograma_de_tres_parcelas_a_partir_de_31_de_janeiro():
    cronograma = build_schedule(date(2026, 1, 31), 3, Decimal("100.00"))

    assert [p["number"] for p in cronograma] == [1, 2, 3]
    assert [p["due_date"] for p in cronograma] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert all(p["amount"] == Decimal("100.00") for p in cronograma)


def test_cronograma_de_uma_parcela():
    cronograma = build_schedule(date(2026, 12, 10), 1, Decimal("250.00"))

    assert cronograma == [{"number": 1, "due_date": date(2026, 12, 10), "amount": Decimal("250.00")}]


@pytest.mark.parametrize(
    "total, quantidade, esperado",
    [
        pytest.param("1200.00", 12, "100.00", id="divisao_exata"),
        pytest.param("1000.00", 3, "333.33", id="arredonda_para_baixo"),
        pytest.param("1000.00", 6, "166.67", id="arredonda_para_cima"),
        pytest.param("1000.00", 12, "83.33", id="dizima"),
    ],
)
def test_estimate_installment_amount(total, quantidade, esperado):
    assert estimate_installment_amount(Decimal(total), quantidade) == Decimal(esperado)