from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class IncomeCreate(BaseModel):
    description: str
    amount: Decimal
    is_fixed: bool
    received_date: date


class IncomeResponse(BaseModel):
    id: int
    description: str
    amount: Decimal
    is_fixed: bool
    received_date: date
    user_id: int

    class Config:
        from_attributes = True