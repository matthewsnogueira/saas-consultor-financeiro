from datetime import date
from decimal import Decimal

from sqlalchemy import func, extract
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


def get_small_expenses(db: Session, current_user: User):
    return (
        db.query(Expense)
        .filter(Expense.user_id == current_user.id)
        .filter(Expense.is_small_expense == True)
        .order_by(Expense.expense_date.desc())
        .all()
    )


def get_small_expenses_summary(db: Session, current_user: User) -> dict:
    today = date.today()

    total_current_month = (
        db.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.user_id == current_user.id)
        .filter(Expense.is_small_expense == True)
        .filter(extract("year", Expense.expense_date) == today.year)
        .filter(extract("month", Expense.expense_date) == today.month)
        .scalar()
    )

    days_elapsed = today.day

    average_daily = Decimal(total_current_month) / days_elapsed if days_elapsed > 0 else Decimal(0)
    projected_monthly = average_daily * 30
    projected_yearly = average_daily * 365

    return {
        "total_current_month": total_current_month,
        "average_daily": round(average_daily, 2),
        "projected_monthly": round(projected_monthly, 2),
        "projected_yearly": round(projected_yearly, 2),
    }