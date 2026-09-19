from sqlalchemy.orm import Session

from app.models.income import Income
from app.models.user import User
from app.schemas.income import IncomeCreate


def create_income(db: Session, income_data: IncomeCreate, current_user: User) -> Income:
    new_income = Income(
        description=income_data.description,
        amount=income_data.amount,
        is_fixed=income_data.is_fixed,
        received_date=income_data.received_date,
        user_id=current_user.id,
    )

    db.add(new_income)
    db.commit()
    db.refresh(new_income)

    return new_income