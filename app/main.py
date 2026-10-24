from fastapi import FastAPI
from app.routes import user, income, expense, debt

app = FastAPI()

app.include_router(user.router)
app.include_router(income.router)
app.include_router(expense.router)
app.include_router(debt.router)

@app.get("/")
def read_root():
    return {"mensagem": "API do SaaS financeiro está no ar"}