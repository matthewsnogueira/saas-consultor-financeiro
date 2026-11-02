from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.debt import Debt, DebtStatus
from app.models.debt_installment import DebtInstallment
from app.models.debt_payment import DebtPayment
from app.models.debt_reported_balance import DebtReportedBalance
from app.models.user import User
from app.schemas.debt import (
    DebtCreate,
    DebtPaymentCreate,
    DebtResponse,
    DebtSettleRequest,
    DelayState,
    InstallmentPreviewRequest,
    InstallmentStatus,
    ReportedBalanceCreate,
    ReportedBalanceResponse,
)
from app.utils.installments import build_schedule, estimate_installment_amount

NOTICE_ESTIMATE = "Valor estimado: pode ser diferente do cobrado pelo credor."
NOTICE_PAID_REACHED_ORIGINAL = (
    "O total pago atingiu o valor original, mas isso não confirma a quitação. "
    "Confirme com o credor."
)
NOTICE_SETTLED_DECLARED = "Dívida quitada em {data}, conforme declarado por você."
NOTICE_SETTLED_CONFIRMED = (
    "Dívida quitada em {data}, com confirmação do credor informada por você."
)

NOTICE_SCHEDULE_LIMITATION = (
    "As parcelas serão criadas mensais e com valores iguais. "
    "Depois de salvar, não será possível editar valores nem vencimentos individualmente."
)
NOTICE_AMOUNT_ESTIMATED = (
    "O valor da parcela é uma estimativa (valor total dividido pela quantidade, sem juros). "
    "Se o contrato tiver um valor de parcela diferente, informe-o."
)
NOTICE_TOTAL_DIFFERS = (
    "A soma das parcelas ({soma}) é diferente do valor total informado ({total}). "
    "Isso é esperado quando há juros ou arredondamento."
)

NOTICE_DELAY_SETTLED = "Dívida quitada, sem atraso."
NOTICE_DELAY_NO_DUE_DATE = (
    "Esta dívida não tem vencimento definido, então não é possível calcular atraso. "
    "Informe um vencimento para acompanhar."
)
NOTICE_DELAY_INSTALLMENTS = (
    "{qtd} parcela(s) vencida(s), faltando {valor}. "
    "Pagamentos registrados sem indicar a parcela não entram nesta conta."
)
NOTICE_DELAY_NONE_OVERDUE = "Nenhuma parcela vencida."
NOTICE_DELAY_ALL_PAID = (
    "Todas as parcelas estão pagas, mas isso não confirma a quitação. "
    "Confirme com o credor."
)
NOTICE_DELAY_INFORMAL_OVERDUE = (
    "O vencimento em {data} já passou. O valor em atraso é uma estimativa "
    "(valor original menos pagamentos registrados, sem juros)."
)
NOTICE_DELAY_INFORMAL_UPCOMING = "Vence em {data}."


def _format_brl(value: Decimal) -> str:
    """Formata um valor em reais no padrão brasileiro: R$ 1.234,56."""
    texto = f"{value:,.2f}"  # 1,234.56
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _resolve_installment_amount(
    original_amount: Decimal, count: int, informed_amount: Decimal | None
) -> tuple[Decimal, bool]:
    """Devolve (valor da parcela, se é estimado). Usado na prévia e no cadastro real."""
    if informed_amount is not None:
        return informed_amount, False

    estimated = estimate_installment_amount(original_amount, count)
    if estimated <= 0:
        raise HTTPException(
            status_code=422,
            detail="O valor total é pequeno demais para dividir nessa quantidade de parcelas.",
        )
    return estimated, True


def compute_installment_state(
    amount: Decimal,
    paid_amount: Decimal,
    due_date: date,
    today: date,
    debt_is_settled: bool,
) -> tuple[InstallmentStatus, int]:
    """Estado da parcela e dias de atraso, sempre calculados na hora (nunca guardados)."""
    if paid_amount >= amount:
        return InstallmentStatus.paga, 0
    if debt_is_settled:
        return InstallmentStatus.encerrada, 0
    if due_date < today:
        return InstallmentStatus.vencida, (today - due_date).days
    if paid_amount > 0:
        return InstallmentStatus.parcial, 0
    return InstallmentStatus.pendente, 0


def compute_debt_delay(
    debt_is_settled: bool,
    due_date: date | None,
    original_amount: Decimal,
    total_paid: Decimal,
    installments: list[dict],
    today: date,
) -> dict:
    """Situação de atraso da dívida, sempre calculada na hora (nunca guardada).

    Dívida com parcelas: o atraso vem das parcelas vencidas.
    Dívida sem parcelas: usa o vencimento único, e o valor em atraso é uma estimativa.
    Dívida sem parcelas e sem vencimento: responde "sem vencimento definido".
    """
    if debt_is_settled:
        return {
            "state": DelayState.quitada,
            "days_overdue": 0,
            "overdue_installments": None,
            "overdue_amount": None,
            "overdue_amount_is_estimated": False,
            "next_due_date": None,
            "notice": NOTICE_DELAY_SETTLED,
        }

    if installments:
        overdue = [i for i in installments if i["status"] == InstallmentStatus.vencida]
        upcoming = [
            i["due_date"]
            for i in installments
            if i["status"] in (InstallmentStatus.pendente, InstallmentStatus.parcial)
        ]
        next_due_date = min(upcoming) if upcoming else None

        if overdue:
            overdue_amount = sum(
                (i["amount"] - i["paid_amount"] for i in overdue), Decimal("0")
            )
            return {
                "state": DelayState.em_atraso,
                "days_overdue": max(i["days_overdue"] for i in overdue),
                "overdue_installments": len(overdue),
                "overdue_amount": overdue_amount,
                "overdue_amount_is_estimated": False,
                "next_due_date": next_due_date,
                "notice": NOTICE_DELAY_INSTALLMENTS.format(
                    qtd=len(overdue), valor=_format_brl(overdue_amount)
                ),
            }

        return {
            "state": DelayState.em_dia,
            "days_overdue": 0,
            "overdue_installments": 0,
            "overdue_amount": Decimal("0"),
            "overdue_amount_is_estimated": False,
            "next_due_date": next_due_date,
            "notice": NOTICE_DELAY_NONE_OVERDUE if upcoming else NOTICE_DELAY_ALL_PAID,
        }

    if due_date is None:
        return {
            "state": DelayState.sem_vencimento_definido,
            "days_overdue": 0,
            "overdue_installments": None,
            "overdue_amount": None,
            "overdue_amount_is_estimated": False,
            "next_due_date": None,
            "notice": NOTICE_DELAY_NO_DUE_DATE,
        }

    if total_paid >= original_amount:
        return {
            "state": DelayState.em_dia,
            "days_overdue": 0,
            "overdue_installments": None,
            "overdue_amount": None,
            "overdue_amount_is_estimated": False,
            "next_due_date": None,
            "notice": NOTICE_PAID_REACHED_ORIGINAL,
        }

    if due_date < today:
        return {
            "state": DelayState.em_atraso,
            "days_overdue": (today - due_date).days,
            "overdue_installments": None,
            "overdue_amount": original_amount - total_paid,
            "overdue_amount_is_estimated": True,
            "next_due_date": None,
            "notice": NOTICE_DELAY_INFORMAL_OVERDUE.format(data=due_date.strftime("%d/%m/%Y")),
        }

    return {
        "state": DelayState.em_dia,
        "days_overdue": 0,
        "overdue_installments": None,
        "overdue_amount": None,
        "overdue_amount_is_estimated": False,
        "next_due_date": due_date,
        "notice": NOTICE_DELAY_INFORMAL_UPCOMING.format(data=due_date.strftime("%d/%m/%Y")),
    }


def preview_installments(preview_data: InstallmentPreviewRequest) -> dict:
    """Mostra o cronograma que seria criado, sem gravar nada."""
    amount, is_estimated = _resolve_installment_amount(
        preview_data.original_amount,
        preview_data.installment_count,
        preview_data.installment_amount,
    )
    schedule = build_schedule(
        preview_data.first_due_date, preview_data.installment_count, amount
    )
    total_of_installments = amount * preview_data.installment_count

    notices = [NOTICE_SCHEDULE_LIMITATION]
    if is_estimated:
        notices.append(NOTICE_AMOUNT_ESTIMATED)
    if total_of_installments != preview_data.original_amount:
        notices.append(
            NOTICE_TOTAL_DIFFERS.format(
                soma=_format_brl(total_of_installments),
                total=_format_brl(preview_data.original_amount),
            )
        )

    return {
        "installments": schedule,
        "installment_amount": amount,
        "amount_is_estimated": is_estimated,
        "total_of_installments": total_of_installments,
        "notices": notices,
    }


def create_debt(db: Session, debt_data: DebtCreate, current_user: User) -> Debt:
    installment_amount = debt_data.installment_amount
    schedule = []

    if debt_data.installment_count is not None:
        installment_amount, _ = _resolve_installment_amount(
            debt_data.original_amount, debt_data.installment_count, installment_amount
        )
        schedule = build_schedule(
            debt_data.due_date, debt_data.installment_count, installment_amount
        )

    new_debt = Debt(
        creditor=debt_data.creditor,
        description=debt_data.description,
        original_amount=debt_data.original_amount,
        monthly_interest_rate=debt_data.monthly_interest_rate,
        installment_amount=installment_amount,
        installment_count=debt_data.installment_count,
        due_date=debt_data.due_date,
        status=DebtStatus.ativa,
        user_id=current_user.id,
    )

    db.add(new_debt)
    # flush envia a dívida ao banco só para ela ganhar um id; nada é confirmado ainda.
    db.flush()

    for item in schedule:
        db.add(
            DebtInstallment(
                debt_id=new_debt.id,
                number=item["number"],
                due_date=item["due_date"],
                amount=item["amount"],
            )
        )

    # Dívida e parcelas são confirmadas juntas: se algo falhar, nada fica salvo.
    db.commit()
    db.refresh(new_debt)

    return new_debt


def get_user_debts(db: Session, current_user: User):
    return (
        db.query(Debt)
        .filter(Debt.user_id == current_user.id)
        .order_by(Debt.created_at.desc())
        .all()
    )


def get_owned_debt(db: Session, debt_id: int, current_user: User) -> Debt:
    """Única porta de entrada para acessar uma dívida pelo id.

    Dívida inexistente e dívida de outro usuário dão a mesma resposta (404),
    para a API não revelar que um id pertence a outra pessoa.
    """
    debt = (
        db.query(Debt)
        .filter(Debt.id == debt_id, Debt.user_id == current_user.id)
        .first()
    )
    if debt is None:
        raise HTTPException(status_code=404, detail="Dívida não encontrada.")
    return debt


def settle_debt(
    db: Session, debt_id: int, settle_data: DebtSettleRequest, current_user: User
) -> Debt:
    debt = get_owned_debt(db, debt_id, current_user)

    if debt.status == DebtStatus.quitada:
        raise HTTPException(status_code=409, detail="A dívida já está quitada.")

    debt.status = DebtStatus.quitada
    debt.settled_at = settle_data.settled_at
    debt.creditor_confirmed = settle_data.creditor_confirmed

    db.commit()
    db.refresh(debt)

    return debt


def reopen_debt(db: Session, debt_id: int, current_user: User) -> Debt:
    debt = get_owned_debt(db, debt_id, current_user)

    if debt.status == DebtStatus.ativa:
        raise HTTPException(status_code=409, detail="A dívida já está ativa.")

    debt.status = DebtStatus.ativa
    debt.settled_at = None
    debt.creditor_confirmed = False

    db.commit()
    db.refresh(debt)

    return debt


def create_payment(
    db: Session, debt_id: int, payment_data: DebtPaymentCreate, current_user: User
) -> DebtPayment:
    debt = get_owned_debt(db, debt_id, current_user)

    if payment_data.installment_id is not None:
        # A parcela é procurada dentro desta dívida: id inexistente ou de outra dívida dá 404.
        installment = (
            db.query(DebtInstallment)
            .filter(
                DebtInstallment.id == payment_data.installment_id,
                DebtInstallment.debt_id == debt.id,
            )
            .first()
        )
        if installment is None:
            raise HTTPException(status_code=404, detail="Parcela não encontrada nesta dívida.")

    new_payment = DebtPayment(
        debt_id=debt.id,
        installment_id=payment_data.installment_id,
        amount=payment_data.amount,
        payment_date=payment_data.payment_date,
        notes=payment_data.notes,
    )

    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    return new_payment


def list_payments(db: Session, debt_id: int, current_user: User):
    debt = get_owned_debt(db, debt_id, current_user)

    return (
        db.query(DebtPayment)
        .filter(DebtPayment.debt_id == debt.id)
        .order_by(DebtPayment.payment_date.desc(), DebtPayment.id.desc())
        .all()
    )


def _installment_rows(db: Session, debt: Debt) -> list[dict]:
    """Parcelas da dívida com valor pago, estado e dias de atraso, calculados na hora."""
    installments = (
        db.query(DebtInstallment)
        .filter(DebtInstallment.debt_id == debt.id)
        .order_by(DebtInstallment.number)
        .all()
    )

    # Uma só consulta soma os pagamentos de todas as parcelas, agrupados por parcela.
    paid_rows = (
        db.query(DebtPayment.installment_id, func.sum(DebtPayment.amount))
        .filter(DebtPayment.debt_id == debt.id, DebtPayment.installment_id.isnot(None))
        .group_by(DebtPayment.installment_id)
        .all()
    )
    paid_by_installment = {installment_id: Decimal(total) for installment_id, total in paid_rows}

    today = date.today()
    debt_is_settled = debt.status == DebtStatus.quitada

    result = []
    for installment in installments:
        paid_amount = paid_by_installment.get(installment.id, Decimal("0"))
        status, days_overdue = compute_installment_state(
            installment.amount, paid_amount, installment.due_date, today, debt_is_settled
        )
        result.append(
            {
                "id": installment.id,
                "debt_id": installment.debt_id,
                "number": installment.number,
                "due_date": installment.due_date,
                "amount": installment.amount,
                "paid_amount": paid_amount,
                "status": status,
                "days_overdue": days_overdue,
            }
        )

    return result


def list_installments(db: Session, debt_id: int, current_user: User) -> list[dict]:
    debt = get_owned_debt(db, debt_id, current_user)
    return _installment_rows(db, debt)


def create_reported_balance(
    db: Session, debt_id: int, balance_data: ReportedBalanceCreate, current_user: User
) -> DebtReportedBalance:
    debt = get_owned_debt(db, debt_id, current_user)

    new_balance = DebtReportedBalance(
        debt_id=debt.id,
        amount=balance_data.amount,
        reference_date=balance_data.reference_date,
    )

    db.add(new_balance)
    db.commit()
    db.refresh(new_balance)

    return new_balance


def get_debt_detail(db: Session, debt_id: int, current_user: User) -> dict:
    debt = get_owned_debt(db, debt_id, current_user)

    # A soma é feita no banco, como nos pequenos gastos.
    total_paid = Decimal(
        db.query(func.coalesce(func.sum(DebtPayment.amount), 0))
        .filter(DebtPayment.debt_id == debt.id)
        .scalar()
    )

    if debt.status == DebtStatus.quitada:
        # Dívida quitada pelo usuário: nada mais a estimar, mesmo que o total pago
        # seja menor que o original (por exemplo, um desconto negociado).
        estimated_balance = Decimal("0")
        data = debt.settled_at.strftime("%d/%m/%Y") if debt.settled_at else "data não informada"
        template = (
            NOTICE_SETTLED_CONFIRMED if debt.creditor_confirmed else NOTICE_SETTLED_DECLARED
        )
        notice = template.format(data=data)
    else:
        # Estimativa sem juros, nunca abaixo de zero.
        estimated_balance = max(debt.original_amount - total_paid, Decimal("0"))
        if total_paid >= debt.original_amount:
            notice = NOTICE_PAID_REACHED_ORIGINAL
        else:
            notice = NOTICE_ESTIMATE

    # Saldo informado pelo usuário: o mais recente pela data de referência.
    # Ele nunca é recalculado a partir dos pagamentos.
    latest_reported = (
        db.query(DebtReportedBalance)
        .filter(DebtReportedBalance.debt_id == debt.id)
        .order_by(
            DebtReportedBalance.reference_date.desc(),
            DebtReportedBalance.created_at.desc(),
            DebtReportedBalance.id.desc(),
        )
        .first()
    )

    delay = compute_debt_delay(
        debt_is_settled=debt.status == DebtStatus.quitada,
        due_date=debt.due_date,
        original_amount=debt.original_amount,
        total_paid=total_paid,
        installments=_installment_rows(db, debt),
        today=date.today(),
    )

    detail = DebtResponse.model_validate(debt).model_dump()
    detail["total_paid"] = total_paid
    detail["estimated_balance"] = estimated_balance
    detail["estimate_notice"] = notice
    detail["reported_balance"] = (
        ReportedBalanceResponse.model_validate(latest_reported) if latest_reported else None
    )
    detail["delay"] = delay
    return detail