import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class DebtStatus(str, enum.Enum):
    ativa = "ativa"
    quitada = "quitada"


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True, index=True)
    creditor = Column(String(150), nullable=False)
    description = Column(String(255), nullable=True)

    # Valor contratado/devido quando a dívida foi cadastrada.
    original_amount = Column(Numeric(12, 2), nullable=False)

    # Opcionais: uma dívida informal pode não ter juros, parcelas nem vencimento.
    monthly_interest_rate = Column(Numeric(7, 4), nullable=True)  # em %, ex: 2.5000
    installment_amount = Column(Numeric(12, 2), nullable=True)
    installment_count = Column(Integer, nullable=True)
    due_date = Column(Date, nullable=True)

    status = Column(Enum(DebtStatus), nullable=False, default=DebtStatus.ativa)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="debts")
    payments = relationship("DebtPayment", back_populates="debt")
    reported_balances = relationship("DebtReportedBalance", back_populates="debt")