from sqlmodel import create_engine, Session, SQLModel
from .models import User, DailySummary, Habit, Meal, MealItem, FoodItem, Exercise

DATABASE_URL = "sqlite:///myfit.db"

engine = create_engine(
    DATABASE_URL,
    echo=True
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session