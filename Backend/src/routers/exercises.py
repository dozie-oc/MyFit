from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import Exercise, ExerciseCatalogItem, ExerciseMuscleMapping, UserGoal
from src.schemas import (
    CardioWeekOut,
    CustomExerciseCreate,
    CustomExerciseUpdate,
    ExerciseCatalogItemOut,
    ExerciseHistoryOut,
    ExerciseLogCreate,
    ExerciseLogUpdate,
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


_CUSTOM_DEFAULT_MET = {
    "strength": 5.0,
    "cardio": 6.0,
    "flexibility": 2.5,
}


def _check_custom_exercise_name_unique(
    session: Session,
    user_id: int,
    name: str,
    exclude_id: int | None = None,
) -> None:
    conds = [
        func.lower(ExerciseCatalogItem.name) == name.strip().lower(),
        *visible_exercise(user_id),
    ]
    if exclude_id is not None:
        conds.append(ExerciseCatalogItem.id != exclude_id)
    clash = session.exec(select(ExerciseCatalogItem).where(*conds)).first()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An exercise with this name already exists.",
        )


def _catalog_item_to_out(
    session: Session,
    item: ExerciseCatalogItem,
) -> ExerciseCatalogItemOut:
    mappings = session.exec(
        select(ExerciseMuscleMapping).where(
            ExerciseMuscleMapping.exercise_catalog_id == item.id
        )
    ).all()
    dto = ExerciseCatalogItemOut.model_validate(item)
    dto.muscles = [ExerciseMuscleMappingOut.model_validate(m) for m in mappings]
    return dto


@router.post(
    "/catalog/custom",
    response_model=ExerciseCatalogItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_exercise(
    data: CustomExerciseCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    _check_custom_exercise_name_unique(session, current_user.id, data.name)
    effective_met = (
        data.met
        if data.met is not None
        else _CUSTOM_DEFAULT_MET.get(data.category, 5.0)
    )
    item = ExerciseCatalogItem(
        name=data.name,
        category=data.category,
        default_met=effective_met,
        description=data.description,
        equipment=data.equipment,
        level=data.level,
        is_custom=True,
        user_id=current_user.id,
    )
    session.add(item)
    session.flush()

    for m in data.muscles:
        session.add(
            ExerciseMuscleMapping(
                exercise_catalog_id=item.id,
                muscle_group=m.muscle_group,
                role=m.role,
            )
        )
    session.commit()
    session.refresh(item)
    return _catalog_item_to_out(session, item)


@router.patch(
    "/catalog/custom/{catalog_id}",
    response_model=ExerciseCatalogItemOut,
)
def update_custom_exercise(
    catalog_id: int,
    data: CustomExerciseUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    item = session.exec(
        select(ExerciseCatalogItem).where(
            ExerciseCatalogItem.id == catalog_id,
            ExerciseCatalogItem.is_custom == True,  # noqa: E712
            ExerciseCatalogItem.user_id == current_user.id,
            ExerciseCatalogItem.deleted_at.is_(None),
        )
    ).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom exercise not found.",
        )

    updates = data.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        _check_custom_exercise_name_unique(
            session, current_user.id, updates["name"], exclude_id=item.id
        )
        item.name = updates["name"]

    new_category = updates.get("category") or item.category
    existing_mappings = session.exec(
        select(ExerciseMuscleMapping).where(
            ExerciseMuscleMapping.exercise_catalog_id == item.id
        )
    ).all()

    if "muscles" in updates and data.muscles is not None:
        final_roles = [m.role for m in data.muscles]
    else:
        final_roles = [m.role for m in existing_mappings]

    if new_category == "strength":
        if "primary" not in final_roles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Strength exercises require at least one primary muscle group.",
            )
    else:
        if "muscles" in updates and data.muscles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cardio and flexibility exercises cannot have muscle mappings.",
            )

    if "category" in updates and updates["category"] is not None:
        item.category = updates["category"]
    if "met" in updates and updates["met"] is not None:
        item.default_met = updates["met"]
    if "equipment" in updates and updates["equipment"] is not None:
        item.equipment = updates["equipment"]
    if "level" in updates and updates["level"] is not None:
        item.level = updates["level"]
    if "description" in updates:
        item.description = updates["description"]

    if ("muscles" in updates and data.muscles is not None) or new_category != "strength":
        for m in existing_mappings:
            session.delete(m)
        session.flush()
        if new_category == "strength" and data.muscles:
            for m in data.muscles:
                session.add(
                    ExerciseMuscleMapping(
                        exercise_catalog_id=item.id,
                        muscle_group=m.muscle_group,
                        role=m.role,
                    )
                )

    session.add(item)
    session.commit()
    session.refresh(item)
    return _catalog_item_to_out(session, item)


@router.delete(
    "/catalog/custom/{catalog_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_custom_exercise(
    catalog_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    item = session.exec(
        select(ExerciseCatalogItem).where(
            ExerciseCatalogItem.id == catalog_id,
            ExerciseCatalogItem.is_custom == True,  # noqa: E712
            ExerciseCatalogItem.user_id == current_user.id,
            ExerciseCatalogItem.deleted_at.is_(None),
        )
    ).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom exercise not found.",
        )

    item.deleted_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()


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
        cardio_week=CardioWeekOut(
            minutes=adequacy.cardio_week.minutes,
            target_minutes=adequacy.cardio_week.target_minutes,
            status=adequacy.cardio_week.status,
        ),
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


def _est_1rm(weight: float | None, reps: int | None) -> float:
    if not weight or weight <= 0 or not reps or reps <= 0:
        return 0.0
    return weight * (1.0 + reps / 30.0)


def _check_is_pr(session: Session, exercise: Exercise) -> bool:
    my_1rm = _est_1rm(exercise.weight_kg, exercise.reps)
    if my_1rm <= 0:
        return False
    conds = [
        Exercise.user_id == exercise.user_id,
        Exercise.deleted_at.is_(None),
        Exercise.id != exercise.id,
    ]
    if exercise.exercise_catalog_id is not None:
        conds.append(Exercise.exercise_catalog_id == exercise.exercise_catalog_id)
    else:
        conds.append(func.lower(Exercise.name) == exercise.name.strip().lower())

    others = session.exec(select(Exercise).where(*conds)).all()
    other_1rms = [
        _est_1rm(o.weight_kg, o.reps)
        for o in others
        if o.weight_kg and o.weight_kg > 0 and o.reps and o.reps > 0
    ]
    if not other_1rms:
        return False
    return my_1rm > max(other_1rms)


def _to_out(exercise: Exercise, is_pr: bool = False) -> ExerciseOut:
    out = ExerciseOut.model_validate(exercise)
    out.is_pr = is_pr
    return out


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

    return _to_out(exercise, is_pr=_check_is_pr(session, exercise))


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
    "/last",
    response_model=ExerciseHistoryOut,
)
def get_exercise_history(
    session: SessionDep,
    current_user: CurrentUserDep,
    exercise_catalog_id: int | None = None,
    name: str | None = None,
):
    if exercise_catalog_id is None and (name is None or not name.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Either exercise_catalog_id or name must be provided.",
        )

    conds = [
        Exercise.user_id == current_user.id,
        Exercise.deleted_at.is_(None),
    ]
    if exercise_catalog_id is not None:
        conds.append(Exercise.exercise_catalog_id == exercise_catalog_id)
    else:
        conds.append(func.lower(Exercise.name) == name.strip().lower())

    logs = session.exec(
        select(Exercise)
        .where(*conds)
        .order_by(Exercise.date.desc(), Exercise.id.desc())
    ).all()

    if not logs:
        return ExerciseHistoryOut(
            last=None,
            best_weight_kg=None,
            best_est_1rm=None,
            times_logged=0,
        )

    weighted = [
        e for e in logs
        if e.weight_kg is not None and e.weight_kg > 0 and e.reps is not None and e.reps > 0
    ]
    best_w = round(max(e.weight_kg for e in weighted), 1) if weighted else None
    best_1rm = round(max(_est_1rm(e.weight_kg, e.reps) for e in weighted), 1) if weighted else None

    return ExerciseHistoryOut(
        last=_to_out(logs[0]),
        best_weight_kg=best_w,
        best_est_1rm=best_1rm,
        times_logged=len(logs),
    )


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


@router.patch(
    "/{exercise_id}",
    response_model=ExerciseOut,
)
def update_exercise(
    exercise_id: int,
    exercise_data: ExerciseLogUpdate,
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

    old_date = exercise.date
    old_name = exercise.name
    updates = exercise_data.model_dump(exclude_unset=True)

    for key, val in updates.items():
        setattr(exercise, key, val)

    name_changed = "name" in updates and updates["name"] is not None and updates["name"].lower() != old_name.lower()
    if name_changed and "exercise_catalog_id" not in updates:
        exercise.exercise_catalog_id = None

    met, cat_item = _resolve_met(session, current_user.id, exercise)
    if name_changed and "exercise_catalog_id" not in updates:
        exercise.exercise_catalog_id = cat_item.id if cat_item else None
    elif cat_item:
        exercise.exercise_catalog_id = cat_item.id

    if cat_item and (not exercise.category or exercise.category == "other"):
        exercise.category = cat_item.category

    user_weight = current_user.weight or 70.0
    calories_burned = calculate_calories(
        user_weight_kg=user_weight,
        met=met,
        duration_minutes=float(exercise.duration_minutes) if exercise.duration_minutes else None,
        sets=exercise.sets,
        intensity=exercise.intensity,
    )

    eff_duration = exercise.duration_minutes
    if (eff_duration is None or eff_duration == 0) and exercise.sets:
        eff_duration = max(5, int(exercise.sets * 2.5))

    rate = (calories_burned / eff_duration) if eff_duration and eff_duration > 0 else 5.0

    exercise.calories_burned = calories_burned
    exercise.calories_burned_per_minute = round(rate, 2)

    session.add(exercise)
    session.commit()
    session.refresh(exercise)

    calculate_daily_summary(session, current_user.id, old_date)
    if exercise.date != old_date:
        calculate_daily_summary(session, current_user.id, exercise.date)

    return _to_out(exercise, is_pr=_check_is_pr(session, exercise))


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