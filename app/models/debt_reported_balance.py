from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class DebtReportedBalance(Base):
    __tablename__ = "debt_reported_balances"

    id = Column(Integer, primary_key=True, index=True)
    debt_id = Column(Integer, ForeignKey("debts.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    reference_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    debt = relationship("Debt", back_populates="reported_balances")