from app.core.database import Base, engine
from app.models.user import User
from app.models.income import Income
from app.models.expense import Expense
from app.models import debt

Base.metadata.create_all(bind=engine)