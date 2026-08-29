from datetime import date, datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from backend.dependencies import CurrentUserDep, SessionDep
from backend.models import Exercise
from backend.schemas import ExerciseLogCreate, ExerciseOut

from backend.routers.daily_summary import calculate_daily_summary


router = APIRouter(
    prefix="/exercises",
    tags=["Exercises"]
)


def exercise_calories(
    exercise: Exercise
) -> float:

    if not exercise.duration_minutes:
        return 0

    return (
        exercise.duration_minutes
        * exercise.calories_burned_per_minute
    )


@router.post(
    "",
    response_model=ExerciseOut,
    status_code=status.HTTP_201_CREATED
)
def create_exercise(
    exercise_data: ExerciseLogCreate,
    session: SessionDep,
    current_user: CurrentUserDep
):

    # MVP calorie rate.
    #
    # Later this should come from an exercise database
    # based on the user's exercise and characteristics.
    calories_burned_per_minute = 5.0

    exercise = Exercise(
        user_id=current_user.id,
        date=exercise_data.date,
        name=exercise_data.name,
        reps=exercise_data.reps,
        duration_minutes=exercise_data.duration_minutes,
        calories_burned_per_minute=calories_burned_per_minute
    )

    session.add(exercise)
    session.commit()
    session.refresh(exercise)

    calculate_daily_summary(
        session,
        current_user.id,
        exercise.date
    )

    return ExerciseOut(
        id=exercise.id,
        date=exercise.date,
        name=exercise.name,
        reps=exercise.reps,
        duration_minutes=exercise.duration_minutes,
        calories_burned=exercise_calories(exercise)
    )


@router.get(
    "",
    response_model=list[ExerciseOut]
)
def get_exercises(
    session: SessionDep,
    current_user: CurrentUserDep,
    exercise_date: date | None = None
):

    statement = select(Exercise).where(
        Exercise.user_id == current_user.id,
        Exercise.deleted_at.is_(None)
    )

    if exercise_date:
        statement = statement.where(
            Exercise.date == exercise_date
        )

    statement = statement.order_by(
        Exercise.date.desc()
    )

    exercises = session.exec(statement).all()

    return [
        ExerciseOut(
            id=exercise.id,
            date=exercise.date,
            name=exercise.name,
            reps=exercise.reps,
            duration_minutes=exercise.duration_minutes,
            calories_burned=exercise_calories(exercise)
        )
        for exercise in exercises
    ]


@router.get(
    "/{exercise_id}",
    response_model=ExerciseOut
)
def get_exercise(
    exercise_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):

    exercise = session.exec(
        select(Exercise).where(
            Exercise.id == exercise_id,
            Exercise.user_id == current_user.id,
            Exercise.deleted_at.is_(None)
        )
    ).first()

    if not exercise:
        raise HTTPException(
            status_code=404,
            detail="Exercise not found"
        )

    return ExerciseOut(
        id=exercise.id,
        date=exercise.date,
        name=exercise.name,
        reps=exercise.reps,
        duration_minutes=exercise.duration_minutes,
        calories_burned=exercise_calories(exercise)
    )


@router.delete(
    "/{exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_exercise(
    exercise_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):

    exercise = session.exec(
        select(Exercise).where(
            Exercise.id == exercise_id,
            Exercise.user_id == current_user.id,
            Exercise.deleted_at.is_(None)
        )
    ).first()

    if not exercise:
        raise HTTPException(
            status_code=404,
            detail="Exercise not found"
        )

    exercise_date = exercise.date

    exercise.deleted_at = datetime.utcnow()

    session.add(exercise)
    session.commit()

    calculate_daily_summary(
        session,
        current_user.id,
        exercise_date
    )

    return None