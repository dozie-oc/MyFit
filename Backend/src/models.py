from datetime import date as Date, datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # Usernames need to be unique at the database level.
    # The index also makes authentication lookups efficient.
    username: str = Field(
        index=True,
        unique=True,
        min_length=3,
        max_length=50,
    )

    hashed_password: str

    # These are the user's current measurements.
    # Historical weight changes are stored separately in WeightLog.
    weight: float = Field(gt=0)
    height: float = Field(gt=0)

    birthdate: Date

    created_at: datetime = Field(
        default_factory=utc_now
    )

    # Soft deletion allows us to retain historical records without
    # physically deleting the user and all related data.
    deleted_at: datetime | None = None


class DailySummary(SQLModel, table=True):
    """
    Cached daily calorie summary for a user.

    The summary is derived from Meal and Exercise records rather than
    being supplied by the client.

    There should only ever be one active summary for a given user/date.
    """

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "date",
            name="uq_daily_summary_user_date",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    date: Date = Field(index=True)

    calories_in: int = Field(ge=0)
    calories_out: int = Field(ge=0)
    net_calories: int

    deleted_at: datetime | None = None


class Habit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    # MVP supports values such as:
    # "daily", "weekly", etc.
    # Validation of the supported values belongs in the schema/service
    # layer rather than the database model.
    frequency: str = Field(
        default="daily",
        max_length=20,
    )

    created_at: datetime = Field(
        default_factory=utc_now
    )

    deleted_at: datetime | None = None


class HabitLog(SQLModel, table=True):
    """
    Records whether a habit was completed on a particular date.

    A habit should have at most one log for a given date.
    """

    __table_args__ = (
        UniqueConstraint(
            "habit_id",
            "date",
            name="uq_habit_log_habit_date",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    habit_id: int = Field(
        foreign_key="habit.id",
        index=True,
    )

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    date: Date = Field(index=True)

    completed: bool


class WeightLog(SQLModel, table=True):
    """
    Historical record of the user's weight.

    The User.weight field represents the user's current/latest weight,
    while this table preserves the historical measurements.
    """

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "date",
            name="uq_weight_log_user_date",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    date: Date = Field(index=True)

    weight: float = Field(gt=0)


class FoodItem(SQLModel, table=True):
    """
    Canonical food record used by the application.

    Nutrition is normalized to a 100g basis. This allows the same food
    to be used with different portions and quantities.

    Example:

        Banana
        calories_per_100g = 89
        protein_per_100g = 1.09
        carbs_per_100g = 22.84
        fat_per_100g = 0.33

    FoodPortion then provides human-friendly measurements such as:

        1 medium banana -> 118g
    """

    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(
        index=True,
        min_length=1,
        max_length=255,
    )

    # USDA FoodData Central ID.
    #
    # Unique because importing the same USDA food twice should not
    # create duplicate FoodItem records.
    #
    # Nullable so that custom foods can be supported later.
    usda_fdc_id: int | None = Field(
        default=None,
        index=True,
        unique=True,
    )

    # Examples:
    # Foundation
    # Branded
    # SR Legacy
    # FNDDS
    usda_data_type: str | None = Field(
        default=None,
        max_length=50,
    )

    # All nutritional values are stored per 100 grams.
    calories_per_100g: float = Field(
        ge=0,
    )

    protein_per_100g: float = Field(
        ge=0,
    )

    carbs_per_100g: float = Field(
        ge=0,
    )

    fat_per_100g: float = Field(
        ge=0,
    )

    # For the MVP, our nutritional calculations are gram-based.
    base_unit: str = Field(
        default="g",
        max_length=10,
    )

    created_at: datetime = Field(
        default_factory=utc_now
    )

    updated_at: datetime = Field(
        default_factory=utc_now
    )

    deleted_at: datetime | None = None


class FoodPortion(SQLModel, table=True):
    """
    Human-friendly measurement for a FoodItem.

    Examples:

        1 large egg -> 50g
        1 medium banana -> 118g
        1 cup cooked rice -> 158g

    gram_weight is the conversion bridge between the portion and the
    FoodItem's normalized per-100g nutritional values.
    """

    id: int | None = Field(default=None, primary_key=True)

    food_id: int = Field(
        foreign_key="fooditem.id",
        index=True,
    )

    # Example: "1 large egg", "1 cup", "1 medium banana".
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    # Number represented by this portion.
    #
    # Usually 1 for "1 egg" or "1 cup", but can also represent other
    # quantities supplied by USDA.
    quantity: float = Field(gt=0)

    # Human-readable unit: egg, cup, banana, tbsp, g, etc.
    unit: str = Field(
        min_length=1,
        max_length=30,
    )

    # Weight of the portion in grams.
    gram_weight: float = Field(gt=0)

    # Original USDA measurement unit, where applicable.
    usda_measure_unit: str | None = Field(
        default=None,
        max_length=30,
    )


class Meal(SQLModel, table=True):
    """
    A meal containing one or more MealItems.

    Nutrition totals are calculated by the backend and stored here as
    a snapshot of the meal at the time it was logged.
    """

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    date: Date = Field(index=True)

    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)

    created_at: datetime = Field(
        default_factory=utc_now
    )

    deleted_at: datetime | None = None


class MealItem(SQLModel, table=True):
    """
    A food consumed as part of a Meal.

    The client selects a FoodItem and optionally a FoodPortion.
    The backend resolves the quantity to grams and calculates nutrition.

    Nutrition is snapshotted here so that historical meals do not
    change if USDA later updates the FoodItem's nutritional values.
    """

    id: int | None = Field(default=None, primary_key=True)

    meal_id: int = Field(
        foreign_key="meal.id",
        index=True,
    )

    food_id: int = Field(
        foreign_key="fooditem.id",
        index=True,
    )

    # Optional portion selected by the user.
    #
    # Example:
    #   food_id = banana
    #   portion_id = medium banana
    #   quantity = 2
    #
    # If portion_id is null, the quantity is interpreted directly
    # according to unit (currently primarily grams).
    portion_id: int | None = Field(
        default=None,
        foreign_key="foodportion.id",
        index=True,
    )

    quantity: float = Field(gt=0)

    unit: str = Field(
        min_length=1,
        max_length=30,
    )

    # Final amount used in the nutritional calculation.
    gram_weight: float = Field(gt=0)

    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)

    deleted_at: datetime | None = None


class Exercise(SQLModel, table=True):
    """
    A logged exercise session.

    calories_burned_per_minute is currently stored with the log so
    historical calorie calculations remain stable even if we later
    change our exercise-calorie estimates.
    """

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    date: Date = Field(index=True)

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

    calories_burned_per_minute: float = Field(
        ge=0,
    )

    created_at: datetime = Field(
        default_factory=utc_now
    )

    deleted_at: datetime | None = None