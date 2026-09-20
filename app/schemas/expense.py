from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, model_validator

from app.models.expense import ExpenseCategory

CATEGORY_SUBCATEGORIES = {
    "alimentacao": ["mercado", "delivery", "restaurante", "lanches"],
    "moradia": ["aluguel", "condominio", "energia", "agua", "internet", "gas"],
    "transporte": ["combustivel", "aplicativo", "transporte_publico", "manutencao", "estacionamento"],
    "saude": ["farmacia", "consulta", "exame", "plano_de_saude", "academia"],
    "educacao": ["curso", "material", "mensalidade"],
    "lazer": ["cinema", "streaming", "viagem", "bar", "eventos"],
    "compras": ["roupas", "eletronicos", "casa", "presentes"],
    "contas_e_servicos": ["telefone", "internet", "seguro"],
    "assinaturas": ["streaming", "software", "revistas"],
    "impostos": ["ir", "iptu", "ipva", "taxas"],
    "cuidados_pessoais": ["cabelo", "estetica", "higiene"],
    "doacoes": ["caridade", "religiosa", "familiar"],
    "outros": ["diversos"],
}


class ExpenseCreate(BaseModel):
    description: str
    amount: Decimal
    is_fixed: bool
    is_small_expense: bool
    category: ExpenseCategory
    subcategory: Optional[str] = None
    expense_date: date

    @model_validator(mode="after")
    def validate_subcategory(self):
        if self.subcategory is None:
            return self

        valid_subcategories = CATEGORY_SUBCATEGORIES.get(self.category.value, [])

        if self.subcategory not in valid_subcategories:
            raise ValueError(
                f"Subcategoria '{self.subcategory}' inválida para a categoria '{self.category.value}'. "
                f"Opções válidas: {', '.join(valid_subcategories)}"
            )

        return self


class ExpenseResponse(BaseModel):
    id: int
    description: str
    amount: Decimal
    is_fixed: bool
    is_small_expense: bool
    category: ExpenseCategory
    subcategory: Optional[str]
    expense_date: date
    user_id: int

    class Config:
        from_attributes = True


class SmallExpensesSummary(BaseModel):
    total_current_month: Decimal
    average_daily: Decimal
    projected_monthly: Decimal
    projected_yearly: Decimal