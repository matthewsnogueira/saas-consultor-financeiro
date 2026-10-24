from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.debt import DebtCreate, DebtResponse
from app.services.debt_service import create_debt, get_user_debts

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