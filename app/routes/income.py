from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.income import IncomeCreate, IncomeResponse
from app.services.income_service import create_income

router = APIRouter(prefix="/incomes", tags=["Incomes"])


@router.post("/", response_model=IncomeResponse)
def register_income(
    income_data: IncomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_income(db, income_data, current_user)