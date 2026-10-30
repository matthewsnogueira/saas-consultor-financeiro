from sqlalchemy import Column, Integer, Numeric, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class DebtInstallment(Base):
    __tablename__ = "debt_installments"
    __table_args__ = (
        UniqueConstraint("debt_id", "number", name="uq_debt_installments_debt_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    debt_id = Column(Integer, ForeignKey("debts.id"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    debt = relationship("Debt", back_populates="installments")
    payments = relationship("DebtPayment", back_populates="installment")