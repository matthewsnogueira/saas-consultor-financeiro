from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.debt import Debt, DebtStatus
from app.models.debt_payment import DebtPayment
from app.models.debt_reported_balance import DebtReportedBalance
from app.models.user import User
from app.schemas.debt import (
    DebtCreate,
    DebtPaymentCreate,
    DebtResponse,
    ReportedBalanceCreate,
    ReportedBalanceResponse,
)

NOTICE_ESTIMATE = "Valor estimado: pode ser diferente do cobrado pelo credor."
NOTICE_PAID_REACHED_ORIGINAL = (
    "O total pago atingiu o valor original, mas isso não confirma a quitação. "
    "Confirme com o credor."
)


def create_debt(db: Session, debt_data: DebtCreate, current_user: User) -> Debt:
    new_debt = Debt(
        creditor=debt_data.creditor,
        description=debt_data.description,
        original_amount=debt_data.original_amount,
        monthly_interest_rate=debt_data.monthly_interest_rate,
        installment_amount=debt_data.installment_amount,
        installment_count=debt_data.installment_count,
        due_date=debt_data.due_date,
        status=DebtStatus.ativa,
        user_id=current_user.id,
    )

    db.add(new_debt)
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


def create_payment(
    db: Session, debt_id: int, payment_data: DebtPaymentCreate, current_user: User
) -> DebtPayment:
    debt = get_owned_debt(db, debt_id, current_user)

    new_payment = DebtPayment(
        debt_id=debt.id,
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

    detail = DebtResponse.model_validate(debt).model_dump()
    detail["total_paid"] = total_paid
    detail["estimated_balance"] = estimated_balance
    detail["estimate_notice"] = notice
    detail["reported_balance"] = (
        ReportedBalanceResponse.model_validate(latest_reported) if latest_reported else None
    )
    return detail