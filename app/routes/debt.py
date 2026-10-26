from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.debt import (
    DebtCreate,
    DebtDetailResponse,
    DebtPaymentCreate,
    DebtPaymentResponse,
    DebtResponse,
    ReportedBalanceCreate,
    ReportedBalanceResponse,
)
from app.services.debt_service import (
    create_debt,
    create_payment,
    create_reported_balance,
    get_debt_detail,
    get_user_debts,
    list_payments,
)

router = APIRouter(prefix="/debts", tags=["Debts"])


@router.post("/", response_model=DebtResponse)
def register_debt(
    debt_data: DebtCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_debt(db, debt_data, current_user)


@router.get("/", response_model=list[DebtResponse])
def list_debts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_debts(db, current_user)


@router.get("/{debt_id}", response_model=DebtDetailResponse)
def debt_detail(
    debt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_debt_detail(db, debt_id, current_user)


@router.post("/{debt_id}/payments", response_model=DebtPaymentResponse)
def register_payment(
    debt_id: int,
    payment_data: DebtPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_payment(db, debt_id, payment_data, current_user)


@router.get("/{debt_id}/payments", response_model=list[DebtPaymentResponse])
def debt_payments(
    debt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_payments(db, debt_id, current_user)


@router.post("/{debt_id}/reported-balance", response_model=ReportedBalanceResponse)
def register_reported_balance(
    debt_id: int,
    balance_data: ReportedBalanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_reported_balance(db, debt_id, balance_data, current_user)