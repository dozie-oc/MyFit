from pydantic import BaseModel, Field
from datetime import datetime, date


# -------------- Input Schemas --------------
class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str
    password: str
    weight: float
    height: float
    #goal: str
    birthdate: date

class UserAuth(BaseModel): 
    """Schema for user authentication."""
    username: str
    password: str

class MealItemCreate(BaseModel):
    """Schema for creating a new meal item entry."""
    #name: str
    quantity: float
    unit: str
    calories: int

class MealCreate(BaseModel):
    items: list[MealItemCreate]

class MealCaloriesOverride(BaseModel):
    """Schema for overriding the calories of a meal."""
    override_calories: float

# class FoodItemCreate(BaseModel):
#     """Schema for creating a new food item entry."""
#     name: str
#     calories_per_unit: int
#     #protein: float
#     #carbs: float
#     #fat: float
    
class HabitCreate(BaseModel):
    """Schema for creating a new habit entry."""
    name: str
    description: str | None = None

class HabitLogCreate(BaseModel):
    """Schema for creating a new habit log entry."""
    date: date
    completed: bool

class WeightLogCreate(BaseModel):
    """Schema for creating a new weight log entry."""
    date: date
    weight: float

class ExerciseLogCreate(BaseModel):
    """Schema for creating a new exercise log entry."""
    date: date
    name: str
    reps: int | None = None
    duration_minutes: int | None = None

# -------------- Output Schemas --------------

class UserOut(BaseModel):
    """Schema for returning the user information, probably for auth"""
    username: str
    weight: float
    height: float
    Age: int
    #goal: str
    #birthdate: date
    

class DailySummaryOut(BaseModel):
    """Schema for returning daily summary information."""
    date: date
    calories_in: int
    calories_out: int
    net_calories: int
    # weight: float
    # steps: int
    
class HabitOut(BaseModel):
    """Schema for returning habit log information."""
    date: date
    name : str
    description: str | None = None
    completed: bool

class MealOut(BaseModel):
    """Schema for returning meal information."""
    date: date
    name: str
    calories: int

class ExerciseOut(BaseModel):
    date : date
    name : str
    duration : int
    reps : int | None = None
    calories_burned : int | None = None

# class FoodItemOut(BaseModel):
#     id: int
#     name: str
#     calories_per_unit: int
#     unit: str
