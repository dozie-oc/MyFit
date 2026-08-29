from pydantic import BaseModel, Field,ConfigDict
from datetime import datetime, date


# ============================================================
# AUTH / USER
# ============================================================

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    weight: float = Field(gt=0)
    height: float = Field(gt=0)

    birthdate: date


class UserAuth(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    weight: float
    height: float
    birthdate: date
    age: int


class Token(BaseModel):
    access_token: str
    token_type: str

# ============================================================
# MEALS
# ============================================================

class MealItemCreate(BaseModel):
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=50)
    calories: int = Field(ge=0)


class MealCreate(BaseModel):
    date: date
    items: list[MealItemCreate] = Field(min_length=1)


class MealCaloriesOverride(BaseModel):
    override_calories: float = Field(ge=0)


class MealItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quantity: float
    unit: str
    calories: int


class MealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    calories: float
    created_at: datetime
    items: list[MealItemOut]


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

class HabitOut(BaseModel):
    """Schema for returning habit log information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    frequency: str


class HabitLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    habit_id: int
    date: date
    completed: bool

# ============================================================
# WEIGHT
# ============================================================

class WeightLogCreate(BaseModel):
    """Schema for creating a new weight log entry."""
    date: date
    weight: float

class WeightLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    weight: float

# ============================================================
# EXERCISE
# ============================================================

class ExerciseLogCreate(BaseModel):
    """Schema for creating a new exercise log entry."""
    date: date
    name: str = Field(min_length=1, max_length=100)
    reps: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(
        default=None,
        ge=0
    )

class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    name: str
    reps: int | None
    duration_minutes: int | None
    calories_burned: float


# ============================================================
# DAILY SUMMARY
# ============================================================

class DailySummaryOut(BaseModel):
    """Schema for returning daily summary information."""
    model_config = ConfigDict(from_attributes=True)

    date: date
    calories_in: int
    calories_out: int
    net_calories: int
