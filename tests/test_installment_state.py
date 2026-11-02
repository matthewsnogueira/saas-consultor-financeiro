from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.schemas.debt import InstallmentStatus
from app.services.debt_service import compute_installment_state

HOJE = date(2026, 10, 30)
CINCO_DIAS_ATRAS = HOJE - timedelta(days=5)
UM_DIA_ATRAS = HOJE - timedelta(days=1)
EM_CINCO_DIAS = HOJE + timedelta(days=5)
AMANHA = HOJE + timedelta(days=1)


@pytest.fixture(autouse=True)
def clean_database():
    """Sobrescreve a fixture do conftest: estes testes não usam banco, então ficam rápidos."""
    yield


@pytest.mark.parametrize(
    "pago, vencimento, quitada, estado_esperado, atraso_esperado",
    [
        pytest.param("100.00", CINCO_DIAS_ATRAS, False, InstallmentStatus.paga, 0, id="paga_exata_mesmo_vencida"),
        pytest.param("120.00", CINCO_DIAS_ATRAS, False, InstallmentStatus.paga, 0, id="paga_acima_do_valor"),
        pytest.param("100.00", CINCO_DIAS_ATRAS, True, InstallmentStatus.paga, 0, id="paga_continua_paga_em_divida_quitada"),
        pytest.param("0", AMANHA, False, InstallmentStatus.pendente, 0, id="pendente_no_futuro"),
        pytest.param("0", HOJE, False, InstallmentStatus.pendente, 0, id="vence_hoje_ainda_e_pendente"),
        pytest.param("0", CINCO_DIAS_ATRAS, False, InstallmentStatus.vencida, 5, id="vencida_com_dias_de_atraso"),
        pytest.param("0", UM_DIA_ATRAS, False, InstallmentStatus.vencida, 1, id="vencida_ontem_atrasa_um_dia"),
        pytest.param("40.00", CINCO_DIAS_ATRAS, False, InstallmentStatus.vencida, 5, id="parcial_vencida_conta_como_vencida"),
        pytest.param("40.00", EM_CINCO_DIAS, False, InstallmentStatus.parcial, 0, id="parcial_dentro_do_prazo"),
        pytest.param("0", CINCO_DIAS_ATRAS, True, InstallmentStatus.encerrada, 0, id="encerrada_nao_conta_atraso"),
        pytest.param("0", EM_CINCO_DIAS, True, InstallmentStatus.encerrada, 0, id="encerrada_no_futuro"),
    ],
)
def test_estado_da_parcela(pago, vencimento, quitada, estado_esperado, atraso_esperado):
    estado, atraso = compute_installment_state(
        Decimal("100.00"), Decimal(pago), vencimento, HOJE, quitada
    )

    assert estado == estado_esperado
    assert atraso == atraso_esperado