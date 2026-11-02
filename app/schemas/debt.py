import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.debt import DebtStatus

# Limite de segurança: evita criar milhares de parcelas por engano.
# Um financiamento imobiliário longo tem em torno de 420 parcelas mensais.
MAX_INSTALLMENTS = 480


class InstallmentStatus(str, enum.Enum):
    paga = "paga"
    parcial = "parcial"
    vencida = "vencida"
    pendente = "pendente"
    encerrada = "encerrada"


class DelayState(str, enum.Enum):
    quitada = "quitada"
    sem_vencimento_definido = "sem_vencimento_definido"
    em_atraso = "em_atraso"
    em_dia = "em_dia"


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
    installment_count: Optional[int] = Field(default=None, ge=1, le=MAX_INSTALLMENTS)
    # Em dívida parcelada, é o vencimento da primeira parcela.
    due_date: Optional[date] = None

    @field_validator("creditor")
    @classmethod
    def creditor_nao_pode_ser_vazio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O credor não pode ser vazio.")
        return value

    @model_validator(mode="after")
    def regras_de_parcelamento(self):
        if self.installment_amount is not None and self.installment_count is None:
            raise ValueError("Informe a quantidade de parcelas junto com o valor da parcela.")
        if self.installment_count is not None and self.due_date is None:
            raise ValueError(
                "Para parcelar, informe o vencimento da primeira parcela (due_date)."
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
    settled_at: Optional[date]
    creditor_confirmed: bool
    created_at: datetime
    user_id: int


class DebtSettleRequest(BaseModel):
    settled_at: date = Field(default_factory=date.today)
    # False = o usuário declara que quitou; True = o usuário afirma que o credor confirmou.
    creditor_confirmed: bool = False

    @field_validator("settled_at")
    @classmethod
    def data_nao_pode_ser_futura(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data da quitação não pode ser no futuro.")
        return value


class InstallmentPreviewRequest(BaseModel):
    original_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    installment_count: int = Field(ge=1, le=MAX_INSTALLMENTS)
    first_due_date: date
    installment_amount: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )


class InstallmentPreviewItem(BaseModel):
    number: int
    due_date: date
    amount: Decimal


class InstallmentPreviewResponse(BaseModel):
    installments: list[InstallmentPreviewItem]
    installment_amount: Decimal
    amount_is_estimated: bool
    total_of_installments: Decimal
    notices: list[str]


class InstallmentResponse(BaseModel):
    id: int
    debt_id: int
    number: int
    due_date: date
    amount: Decimal
    paid_amount: Decimal
    status: InstallmentStatus
    days_overdue: int


class DebtPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment_date: date = Field(default_factory=date.today)
    notes: Optional[str] = Field(default=None, max_length=255)
    # Opcional: a qual parcela este pagamento se refere.
    installment_id: Optional[int] = Field(default=None, ge=1)

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
    installment_id: Optional[int]
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


class DebtDelay(BaseModel):
    state: DelayState
    days_overdue: int
    # Só preenchido quando a dívida tem parcelas.
    overdue_installments: Optional[int] = None
    overdue_amount: Optional[Decimal] = None
    # True quando o valor em atraso é uma estimativa (dívida sem parcelas).
    overdue_amount_is_estimated: bool = False
    next_due_date: Optional[date] = None
    notice: str


class DebtDetailResponse(DebtResponse):
    total_paid: Decimal
    estimated_balance: Decimal
    estimate_notice: str
    reported_balance: Optional[ReportedBalanceResponse] = None
    delay: DebtDelay