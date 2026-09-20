from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import ExpenseCreate


def create_expense(db: Session, expense_data: ExpenseCreate, current_user: User) -> Expense:
    new_expense = Expense(
        description=expense_data.description,
        amount=expense_data.amount,
        is_fixed=expense_data.is_fixed,
        is_small_expense=expense_data.is_small_expense,
        category=expense_data.category,
        subcategory=expense_data.subcategory,
        expense_date=expense_data.expense_date,
        user_id=current_user.id,
    )

    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)

    return new_expense