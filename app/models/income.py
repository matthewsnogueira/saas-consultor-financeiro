from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Income(Base):
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    is_fixed = Column(Boolean, nullable=False, default=False)
    received_date = Column(Date, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="incomes")