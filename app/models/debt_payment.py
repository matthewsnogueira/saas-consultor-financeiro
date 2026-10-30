from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class DebtPayment(Base):
    __tablename__ = "debt_payments"

    id = Column(Integer, primary_key=True, index=True)
    debt_id = Column(Integer, ForeignKey("debts.id"), nullable=False, index=True)

    # Opcional: a qual parcela este pagamento se refere. Sem isso, o pagamento
    # conta no total pago da dívida, mas não quita nenhuma parcela.
    installment_id = Column(Integer, ForeignKey("debt_installments.id"), nullable=True, index=True)

    amount = Column(Numeric(12, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    debt = relationship("Debt", back_populates="payments")
    installment = relationship("DebtInstallment", back_populates="payments")