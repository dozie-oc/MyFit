from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import Exercise, ExerciseCatalogItem, ExerciseMuscleMapping, UserGoal
from src.schemas import (
    ExerciseCatalogItemOut,
    ExerciseLogCreate,
    ExerciseMuscleMappingOut,
    ExerciseOut,
    TrainingAdequacyResponse,
    MuscleGroupStatus,
)
from src.routers.daily_summary import calculate_daily_summary
from src.services.exercise_access import visible_exercise
from src.services.training_service import (
    INTENSITY_MULTIPLIERS,
    evaluate_training_adequacy,
)


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

    mult = INTENSITY_MULTIPLIERS.get((intensity or "").lower(), 1.0)
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
        *visible_exercise(current_user.id),
    )

    if category:
        query = query.where(ExerciseCatalogItem.category == category.lower())

    query = query.order_by(ExerciseCatalogItem.category, ExerciseCatalogItem.name)
    items = session.exec(query).all()
    if not items:
        return []

    item_ids = [item.id for item in items if item.id is not None]
    mappings = session.exec(
        select(ExerciseMuscleMapping).where(
            ExerciseMuscleMapping.exercise_catalog_id.in_(item_ids)
        )
    ).all()
    muscles_by_item: dict[int, list[ExerciseMuscleMappingOut]] = {}
    for m in mappings:
        muscles_by_item.setdefault(m.exercise_catalog_id, []).append(
            ExerciseMuscleMappingOut.model_validate(m)
        )

    out: list[ExerciseCatalogItemOut] = []
    for item in items:
        dto = ExerciseCatalogItemOut.model_validate(item)
        dto.muscles = muscles_by_item.get(item.id, [])
        out.append(dto)
    return out


@router.get(
    "/adequacy",
    response_model=TrainingAdequacyResponse,
)
def get_training_adequacy(
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Evaluate the authenticated user's current training adequacy.

    Returns structured information about:
    - Overall training status (insufficient / adequate / high)
    - Per-muscle-group coverage with set counts and targets
    - Recommended next action (continue / adequate / rest)
    - Suggested next exercises based on undertrained areas
    - Human-readable summary and detail text
    """
    goal: UserGoal | None = session.exec(
        select(UserGoal).where(UserGoal.user_id == current_user.id)
    ).first()

    adequacy = evaluate_training_adequacy(
        session=session,
        user_id=current_user.id,
        goal=goal,
    )

    muscle_group_statuses = [
        MuscleGroupStatus(
            muscle_group=mv.muscle_group,
            status=mv.status,
            sets_completed=mv.effective_sets,
            target_min=mv.target_min,
            target_max=mv.target_max,
        )
        for mv in adequacy.muscle_volumes.values()
    ]

    return TrainingAdequacyResponse(
        overall_status=adequacy.overall_status,
        session_action=adequacy.session_action,
        muscle_groups=muscle_group_statuses,
        recommended_next=adequacy.recommended_next,
        summary=adequacy.summary,
        detail=adequacy.detail,
        exercises_today=adequacy.exercises_today,
        total_sets_today=adequacy.total_sets_today,
    )


# ============================================================
# EXERCISE LOGGING
# ============================================================


def _resolve_met(
    session: Session,
    user_id: int,
    data,
) -> tuple[float, ExerciseCatalogItem | None]:
    cat_id = getattr(data, "exercise_catalog_id", None)
    if cat_id:
        cat_item = session.exec(
            select(ExerciseCatalogItem).where(
                ExerciseCatalogItem.id == cat_id,
                *visible_exercise(user_id),
            )
        ).first()
        if not cat_item:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exercise not found in catalog.",
            )
        return cat_item.default_met, cat_item

    cat_item = session.exec(
        select(ExerciseCatalogItem).where(
            func.lower(ExerciseCatalogItem.name) == data.name.strip().lower(),
            *visible_exercise(user_id),
        )
    ).first()
    if cat_item:
        return cat_item.default_met, cat_item

    name_lower = data.name.lower()
    for kw, kw_met in KEYWORD_MET.items():
        if kw in name_lower:
            return kw_met, None

    cat_str = (getattr(data, "category", None) or "other").lower()
    return DEFAULT_CATEGORY_MET.get(cat_str, 5.0), None


def _to_out(exercise: Exercise) -> ExerciseOut:
    return ExerciseOut.model_validate(exercise)


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
    met, cat_item = _resolve_met(session, current_user.id, exercise_data)
    if cat_item:
        exercise_data.exercise_catalog_id = cat_item.id
        if not exercise_data.category or exercise_data.category == "other":
            exercise_data.category = cat_item.category

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
        rir=exercise_data.rir,
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

    return _to_out(exercise)


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

    return [_to_out(e) for e in exercises]


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

    return _to_out(exercise)


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