from app.core.database import Base, engine
from app.models.user import User
from app.models.income import Income

Base.metadata.create_all(bind=engine)