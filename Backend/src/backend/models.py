from sqlmodel import Field, SQLModel
from datetime import date, datetime

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    username: str
    #name: str
    hashed_password: str
    weight: float
    height: float
    # goal: str
    birthdate: date
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None
    #is_active: bool = True

class DailySummary(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")

    date: date
    #weight: float
    calories_in: int
    calories_out: int
    net_calories: int
    #steps: int
    deleted_at: datetime | None = None

class Habit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")

    name: str
    description: str | None = None
    frequency: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None


class HabitLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habit.id")
    user_id: int = Field(foreign_key="user.id")

    date: date
    completed: bool

class WeightLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")

    date: date
    weight: float

class Meal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")

    date: date
    calories: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

class MealItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    meal_id: int = Field(foreign_key="meal.id")
    #food_id: int = Field(foreign_key="fooditem.id")
    
    #food_name: str
    quantity: float
    unit: str
    calories: int
    # protein: float
    # carbs: float
    # fat: float
    deleted_at: datetime | None = None

#class FoodItem(SQLModel, table=True):
#    id: int | None = Field(default=None, primary_key=True)
#    name: str
#    calories_per_unit: float
#    unit : str
#    #protein: float
#    #carbs: float
#    #fat: float
#    deleted_at: datetime | None = None

class Exercise(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")

    date: date
    name: str
    reps: int | None = None
    duration_minutes: int | None = None

    calories_burned_per_minute: float

    created_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None