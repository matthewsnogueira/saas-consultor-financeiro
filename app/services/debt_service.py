from sqlalchemy.orm import Session

from app.models.debt import Debt, DebtStatus
from app.models.user import User
from app.schemas.debt import DebtCreate


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