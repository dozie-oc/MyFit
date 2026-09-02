from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select, or_

from src.dependencies import CurrentUserDep, SessionDep
from src.models import Exercise, ExerciseCatalogItem
from src.schemas import ExerciseCatalogItemOut, ExerciseLogCreate, ExerciseOut
from src.routers.daily_summary import calculate_daily_summary


router = APIRouter(
    prefix="/exercises",
    tags=["Exercises"]
)

# Standard fallback MET by category
DEFAULT_CATEGORY_MET = {
    "cardio": 7.0,
    "strength": 5.0,
    "flexibility": 2.8,
    "sports": 6.5,
    "other": 5.0,
}

# Standard fallback MET by common keywords
KEYWORD_MET = {
    "running": 9.8,
    "jogging": 7.0,
    "cycling": 7.5,
    "biking": 7.5,
    "swimming": 7.0,
    "walking": 3.8,
    "jump rope": 11.0,
    "hiit": 8.0,
    "yoga": 2.8,
    "pilates": 3.0,
    "rowing": 7.0,
    "elliptical": 6.5,
    "bench press": 5.0,
    "squat": 5.0,
    "deadlift": 5.0,
    "weight": 5.0,
    "push-up": 4.5,
    "pull-up": 4.5,
}

INTENSITY_MULTIPLIER = {
    "low": 0.8,
    "moderate": 1.0,
    "high": 1.25,
}


def calculate_calories(
    user_weight_kg: float,
    met: float,
    duration_minutes: float | None,
    sets: int | None,
    intensity: str | None,
) -> float:
    """
    Calculate estimated calories burned based on MET, duration, intensity, and user weight.

    Formula: Calories = (MET * 3.5 * weight_kg / 200) * duration_minutes
    """
    if user_weight_kg <= 0:
        user_weight_kg = 70.0  # Safe fallback weight

    mult = INTENSITY_MULTIPLIER.get((intensity or "").lower(), 1.0)
    effective_met = met * mult

    if duration_minutes is not None and duration_minutes > 0:
        mins = duration_minutes
    elif sets is not None and sets > 0:
        # Estimate ~2.5 minutes per set for strength training
        mins = max(5.0, sets * 2.5)
    else:
        mins = 0.0

    if mins <= 0:
        return 0.0

    calories = (effective_met * 3.5 * user_weight_kg / 200.0) * mins
    return round(calories, 1)


# ============================================================
# EXERCISE CATALOG
# ============================================================


@router.get(
    "/catalog",
    response_model=list[ExerciseCatalogItemOut],
)
def get_exercise_catalog(
    session: SessionDep,
    current_user: CurrentUserDep,
    category: str | None = None,
):
    """
    Retrieve standard exercise catalogue items and user-defined custom exercises.
    """
    query = select(ExerciseCatalogItem).where(
        or_(
            ExerciseCatalogItem.is_custom == False,  # Standard catalog
            ExerciseCatalogItem.user_id == current_user.id,  # User custom
        ),
        ExerciseCatalogItem.deleted_at.is_(None),
    )

    if category:
        query = query.where(ExerciseCatalogItem.category == category.lower())

    query = query.order_by(ExerciseCatalogItem.category, ExerciseCatalogItem.name)
    return session.exec(query).all()


# ============================================================
# EXERCISE LOGGING
# ============================================================


@router.post(
    "",
    response_model=ExerciseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_exercise(
    exercise_data: ExerciseLogCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Log an exercise session with flexible strength or cardio tracking.
    Calories burned are calculated using MET, duration, intensity, and user weight.
    """
    # 1. Determine MET from catalogue item, name keyword, or category
    met = DEFAULT_CATEGORY_MET.get(exercise_data.category.lower(), 5.0)

    if exercise_data.exercise_catalog_id:
        cat_item = session.get(ExerciseCatalogItem, exercise_data.exercise_catalog_id)
        if cat_item:
            met = cat_item.default_met
            if not exercise_data.category or exercise_data.category == "other":
                exercise_data.category = cat_item.category
    else:
        # Check keyword matches
        name_lower = exercise_data.name.lower()
        for kw, kw_met in KEYWORD_MET.items():
            if kw in name_lower:
                met = kw_met
                break

    # 2. Compute calories burned
    user_weight = current_user.weight or 70.0
    calories_burned = calculate_calories(
        user_weight_kg=user_weight,
        met=met,
        duration_minutes=float(exercise_data.duration_minutes) if exercise_data.duration_minutes else None,
        sets=exercise_data.sets,
        intensity=exercise_data.intensity,
    )

    eff_duration = exercise_data.duration_minutes
    if (eff_duration is None or eff_duration == 0) and exercise_data.sets:
        eff_duration = max(5, int(exercise_data.sets * 2.5))

    rate = (calories_burned / eff_duration) if eff_duration and eff_duration > 0 else 5.0

    exercise = Exercise(
        user_id=current_user.id,
        date=exercise_data.date,
        name=exercise_data.name,
        category=exercise_data.category,
        exercise_catalog_id=exercise_data.exercise_catalog_id,
        sets=exercise_data.sets,
        reps=exercise_data.reps,
        weight_kg=exercise_data.weight_kg,
        duration_minutes=exercise_data.duration_minutes,
        distance_km=exercise_data.distance_km,
        intensity=exercise_data.intensity,
        calories_burned_per_minute=round(rate, 2),
        calories_burned=calories_burned,
    )

    session.add(exercise)
    session.commit()
    session.refresh(exercise)

    calculate_daily_summary(
        session,
        current_user.id,
        exercise.date,
    )

    return ExerciseOut(
        id=exercise.id,
        date=exercise.date,
        name=exercise.name,
        category=exercise.category,
        exercise_catalog_id=exercise.exercise_catalog_id,
        sets=exercise.sets,
        reps=exercise.reps,
        weight_kg=exercise.weight_kg,
        duration_minutes=exercise.duration_minutes,
        distance_km=exercise.distance_km,
        intensity=exercise.intensity,
        calories_burned=exercise.calories_burned,
    )


@router.get(
    "",
    response_model=list[ExerciseOut],
)
def get_exercises(
    session: SessionDep,
    current_user: CurrentUserDep,
    exercise_date: date | None = None,
):
    statement = select(Exercise).where(
        Exercise.user_id == current_user.id,
        Exercise.deleted_at.is_(None),
    )

    if exercise_date:
        statement = statement.where(
            Exercise.date == exercise_date
        )

    statement = statement.order_by(
        Exercise.date.desc(),
        Exercise.id.desc(),
    )

    exercises = session.exec(statement).all()

    return [
        ExerciseOut(
            id=e.id,
            date=e.date,
            name=e.name,
            category=e.category,
            exercise_catalog_id=e.exercise_catalog_id,
            sets=e.sets,
            reps=e.reps,
            weight_kg=e.weight_kg,
            duration_minutes=e.duration_minutes,
            distance_km=e.distance_km,
            intensity=e.intensity,
            calories_burned=e.calories_burned if e.calories_burned > 0 else (
                (e.duration_minutes or 0) * e.calories_burned_per_minute
            ),
        )
        for e in exercises
    ]


@router.get(
    "/{exercise_id}",
    response_model=ExerciseOut,
)
def get_exercise(
    exercise_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    exercise = session.exec(
        select(Exercise).where(
            Exercise.id == exercise_id,
            Exercise.user_id == current_user.id,
            Exercise.deleted_at.is_(None),
        )
    ).first()

    if not exercise:
        raise HTTPException(
            status_code=404,
            detail="Exercise not found",
        )

    return ExerciseOut(
        id=exercise.id,
        date=exercise.date,
        name=exercise.name,
        category=exercise.category,
        exercise_catalog_id=exercise.exercise_catalog_id,
        sets=exercise.sets,
        reps=exercise.reps,
        weight_kg=exercise.weight_kg,
        duration_minutes=exercise.duration_minutes,
        distance_km=exercise.distance_km,
        intensity=exercise.intensity,
        calories_burned=exercise.calories_burned if exercise.calories_burned > 0 else (
            (exercise.duration_minutes or 0) * exercise.calories_burned_per_minute
        ),
    )


@router.delete(
    "/{exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_exercise(
    exercise_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    exercise = session.exec(
        select(Exercise).where(
            Exercise.id == exercise_id,
            Exercise.user_id == current_user.id,
            Exercise.deleted_at.is_(None),
        )
    ).first()

    if not exercise:
        raise HTTPException(
            status_code=404,
            detail="Exercise not found",
        )

    exercise_date = exercise.date
    exercise.deleted_at = datetime.now(timezone.utc)

    session.add(exercise)
    session.commit()

    calculate_daily_summary(
        session,
        current_user.id,
        exercise_date,
    )

    return None