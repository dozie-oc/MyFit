from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from backend.dependencies import CurrentUserDep, SessionDep
from backend.models import Habit, HabitLog
from backend.schemas import (
    HabitCreate,
    HabitLogCreate,
    HabitLogOut,
    HabitOut,
)


router = APIRouter(
    prefix="/habits",
    tags=["Habits"]
)


@router.post(
    "",
    response_model=HabitOut,
    status_code=status.HTTP_201_CREATED
)
def create_habit(
    habit_data: HabitCreate,
    session: SessionDep,
    current_user: CurrentUserDep
):

    habit = Habit(
        user_id=current_user.id,
        name=habit_data.name,
        description=habit_data.description,
        frequency="daily"
    )

    session.add(habit)
    session.commit()
    session.refresh(habit)

    return habit


@router.get(
    "",
    response_model=list[HabitOut]
)
def get_habits(
    session: SessionDep,
    current_user: CurrentUserDep
):

    habits = session.exec(
        select(Habit).where(
            Habit.user_id == current_user.id,
            Habit.deleted_at.is_(None)
        )
    ).all()

    return habits


@router.get(
    "/{habit_id}",
    response_model=HabitOut
)
def get_habit(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):

    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
            Habit.deleted_at.is_(None)
        )
    ).first()

    if not habit:
        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    return habit


@router.post(
    "/{habit_id}/logs",
    response_model=HabitLogOut
)
def log_habit(
    habit_id: int,
    log_data: HabitLogCreate,
    session: SessionDep,
    current_user: CurrentUserDep
):

    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
            Habit.deleted_at.is_(None)
        )
    ).first()

    if not habit:
        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    existing_log = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id == habit_id,
            HabitLog.user_id == current_user.id,
            HabitLog.date == log_data.date
        )
    ).first()

    if existing_log:

        existing_log.completed = (
            log_data.completed
        )

        session.add(existing_log)
        session.commit()
        session.refresh(existing_log)

        return existing_log

    habit_log = HabitLog(
        habit_id=habit_id,
        user_id=current_user.id,
        date=log_data.date,
        completed=log_data.completed
    )

    session.add(habit_log)
    session.commit()
    session.refresh(habit_log)

    return habit_log


@router.get(
    "/{habit_id}/logs",
    response_model=list[HabitLogOut]
)
def get_habit_logs(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):

    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
            Habit.deleted_at.is_(None)
        )
    ).first()

    if not habit:
        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    logs = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id == habit_id,
            HabitLog.user_id == current_user.id
        ).order_by(
            HabitLog.date.desc()
        )
    ).all()

    return logs


@router.delete(
    "/{habit_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_habit(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):

    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
            Habit.deleted_at.is_(None)
        )
    ).first()

    if not habit:
        raise HTTPException(
            status_code=404,
            detail="Habit not found"
        )

    habit.deleted_at = datetime.utcnow()

    session.add(habit)
    session.commit()

    return None