from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class DebtPayment(Base):
    __tablename__ = "debt_payments"

    id = Column(Integer, primary_key=True, index=True)
    debt_id = Column(Integer, ForeignKey("debts.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    debt = relationship("Debt", back_populates="payments")