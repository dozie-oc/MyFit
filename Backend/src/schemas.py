from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# AUTH / USER
# ============================================================


class UserCreate(BaseModel):
    """Input required to create a new user."""

    username: str = Field(
        min_length=3,
        max_length=50,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    weight: float = Field(gt=0)
    height: float = Field(gt=0)

    birthdate: date


class UserAuth(BaseModel):
    """Credentials supplied during login."""

    username: str = Field(
        min_length=1,
        max_length=50,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class UserOut(BaseModel):
    """Public representation of the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    weight: float
    height: float
    birthdate: date
    age: int


class Token(BaseModel):
    """JWT authentication response."""

    access_token: str
    token_type: str


# ============================================================
# FOODS
# ============================================================


class FoodSearchResult(BaseModel):
    """
    Simplified representation of a USDA search result.

    We deliberately don't expose the entire USDA response to Flutter.
    The USDA API remains an implementation detail of our backend.
    """

    fdc_id: int
    name: str
    data_type: str | None = None


class FoodSearchResponse(BaseModel):
    """Response returned by the food search endpoint."""

    foods: list[FoodSearchResult]
    total_hits: int


class FoodImportRequest(BaseModel):
    """
    Optional request body for importing a USDA food.

    The FDC ID itself is normally supplied as part of the URL, e.g.
        POST /foods/import/12345

    Keeping this schema empty is unnecessary, so no request body is
    required for the current MVP.
    """

    pass


class FoodPortionOut(BaseModel):
    """A human-friendly serving size for a FoodItem."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float
    unit: str
    gram_weight: float
    usda_measure_unit: str | None


class FoodItemOut(BaseModel):
    """Food stored in our local database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

    usda_fdc_id: int | None
    usda_data_type: str | None

    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float

    base_unit: str

    portions: list[FoodPortionOut] = Field(
        default_factory=list
    )


# ============================================================
# MEALS
# ============================================================


class MealItemCreate(BaseModel):
    """
    A food consumed as part of a meal.

    There are two supported input modes.

    1. Food portion:

        {
            "food_id": 15,
            "portion_id": 4,
            "quantity": 2
        }

        If portion 4 represents 118g, this means:
            2 × 118g = 236g

    2. Direct grams:

        {
            "food_id": 15,
            "quantity": 150,
            "unit": "g"
        }

    The service layer is responsible for resolving the actual
    gram weight and calculating the nutrition.
    """

    food_id: int = Field(gt=0)

    quantity: float = Field(
        gt=0,
        le=100000,
    )

    portion_id: int | None = Field(
        default=None,
        gt=0,
    )

    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str | None) -> str | None:
        """Normalize units before they reach the service layer."""

        if value is None:
            return None

        return value.strip().lower()


class MealCreate(BaseModel):
    """Input required to create a meal."""

    date: date

    items: list[MealItemCreate] = Field(
        min_length=1,
        max_length=100,
    )


class MealCaloriesOverride(BaseModel):
    """
    Allows the user to override the calculated meal calorie total.

    This does not alter the underlying FoodItem or MealItem nutrition.
    It only changes the Meal's calorie total.
    """

    override_calories: float = Field(
        ge=0,
        le=1_000_000,
    )


class MealItemOut(BaseModel):
    """Stored nutritional snapshot of a meal item."""

    model_config = ConfigDict(from_attributes=True)

    id: int

    food_id: int
    portion_id: int | None

    quantity: float
    unit: str

    gram_weight: float

    calories: float
    protein: float
    carbs: float
    fat: float


class MealOut(BaseModel):
    """Complete meal including its food items."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date

    calories: float
    protein: float
    carbs: float
    fat: float

    created_at: datetime

    items: list[MealItemOut] = Field(
        default_factory=list
    )


# ============================================================
# HABITS
# ============================================================


class HabitCreate(BaseModel):
    """Input required to create a habit."""

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=500,
    )


class HabitLogCreate(BaseModel):
    """Input for marking a habit as completed/not completed."""

    date: date
    completed: bool


class HabitOut(BaseModel):
    """Public representation of a user's habit."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    frequency: str


class HabitLogOut(BaseModel):
    """Public representation of a habit log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    habit_id: int
    date: date
    completed: bool


# ============================================================
# WEIGHT
# ============================================================


class WeightLogCreate(BaseModel):
    """Input for recording a weight measurement."""

    date: date

    weight: float = Field(
        gt=0,
        le=500,
    )


class WeightLogOut(BaseModel):
    """Public representation of a weight log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    weight: float


# ============================================================
# EXERCISE
# ============================================================


class ExerciseLogCreate(BaseModel):
    """
    Input for recording exercise.

    The client does NOT supply calories burned per minute.
    That value is controlled by the backend so the client cannot
    arbitrarily manipulate calorie expenditure.
    """

    date: date

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    reps: int | None = Field(
        default=None,
        ge=0,
    )

    duration_minutes: int | None = Field(
        default=None,
        gt=0,
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class ExerciseOut(BaseModel):
    """Public representation of a logged exercise."""

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
    """Calculated calorie summary for a particular date."""

    model_config = ConfigDict(from_attributes=True)

    date: date
    calories_in: int
    calories_out: int
    net_calories: int
