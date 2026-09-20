from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseResponse, SmallExpensesSummary
from app.services.expense_service import create_expense, get_small_expenses, get_small_expenses_summary

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.post("/", response_model=ExpenseResponse)
def register_expense(
    expense_data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_expense(db, expense_data, current_user)


@router.get("/small", response_model=list[ExpenseResponse])
def list_small_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_small_expenses(db, current_user)


@router.get("/small/summary", response_model=SmallExpensesSummary)
def small_expenses_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_small_expenses_summary(db, current_user)