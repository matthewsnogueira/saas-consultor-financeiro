from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.debt import DebtStatus


class DebtCreate(BaseModel):
    creditor: str = Field(max_length=150)
    description: Optional[str] = Field(default=None, max_length=255)
    original_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    monthly_interest_rate: Optional[Decimal] = Field(
        default=None, ge=0, le=100, max_digits=7, decimal_places=4
    )
    installment_amount: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    installment_count: Optional[int] = Field(default=None, ge=1)
    due_date: Optional[date] = None

    @field_validator("creditor")
    @classmethod
    def creditor_nao_pode_ser_vazio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O credor não pode ser vazio.")
        return value

    @model_validator(mode="after")
    def parcela_e_quantidade_juntas(self):
        tem_valor = self.installment_amount is not None
        tem_quantidade = self.installment_count is not None
        if tem_valor != tem_quantidade:
            raise ValueError(
                "Informe o valor da parcela e a quantidade de parcelas juntos, ou nenhum dos dois."
            )
        return self


class DebtResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creditor: str
    description: Optional[str]
    original_amount: Decimal
    monthly_interest_rate: Optional[Decimal]
    installment_amount: Optional[Decimal]
    installment_count: Optional[int]
    due_date: Optional[date]
    status: DebtStatus
    created_at: datetime
    user_id: int


class DebtPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment_date: date = Field(default_factory=date.today)
    notes: Optional[str] = Field(default=None, max_length=255)

    @field_validator("payment_date")
    @classmethod
    def data_nao_pode_ser_futura(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data do pagamento não pode ser no futuro.")
        return value


class DebtPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    debt_id: int
    amount: Decimal
    payment_date: date
    notes: Optional[str]
    created_at: datetime


class ReportedBalanceCreate(BaseModel):
    # ge=0: o usuário pode informar que não deve mais nada (saldo zero).
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    reference_date: date = Field(default_factory=date.today)

    @field_validator("reference_date")
    @classmethod
    def data_nao_pode_ser_futura(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data do saldo não pode ser no futuro.")
        return value


class ReportedBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    debt_id: int
    amount: Decimal
    reference_date: date
    created_at: datetime


class DebtDetailResponse(DebtResponse):
    total_paid: Decimal
    estimated_balance: Decimal
    estimate_notice: str
    reported_balance: Optional[ReportedBalanceResponse] = None