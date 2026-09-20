import enum
from sqlalchemy import Column, Integer, String, Numeric, Boolean, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.database import Base


class ExpenseCategory(str, enum.Enum):
    ALIMENTACAO = "alimentacao"
    MORADIA = "moradia"
    TRANSPORTE = "transporte"
    SAUDE = "saude"
    EDUCACAO = "educacao"
    LAZER = "lazer"
    COMPRAS = "compras"
    CONTAS_E_SERVICOS = "contas_e_servicos"
    ASSINATURAS = "assinaturas"
    IMPOSTOS = "impostos"
    CUIDADOS_PESSOAIS = "cuidados_pessoais"
    DOACOES = "doacoes"
    OUTROS = "outros"


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    is_fixed = Column(Boolean, nullable=False, default=False)
    is_small_expense = Column(Boolean, nullable=False, default=False)
    category = Column(SQLEnum(ExpenseCategory), nullable=False)
    subcategory = Column(String, nullable=True)
    expense_date = Column(Date, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="expenses")