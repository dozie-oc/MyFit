from datetime import date

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import (
    DailySummary,
    Exercise,
    Meal,
)
from src.schemas import DailySummaryOut


router = APIRouter(
    prefix="/summary",
    tags=["Daily Summary"]
)


def compute_daily_summary_transient(
    session: Session,
    user_id: int,
    summary_date: date
) -> DailySummary:
    """
    Compute a day's summary from Meal and Exercise records WITHOUT
    persisting anything. Safe to call from read-only (GET) endpoints.
    """

    meals = session.exec(
        select(Meal).where(
            Meal.user_id == user_id,
            Meal.date == summary_date,
            Meal.deleted_at.is_(None)
        )
    ).all()

    exercises = session.exec(
        select(Exercise).where(
            Exercise.user_id == user_id,
            Exercise.date == summary_date,
            Exercise.deleted_at.is_(None)
        )
    ).all()

    calories_in = int(
        sum(
            meal.calories
            for meal in meals
        )
    )

    calories_out = int(
        sum(
            exercise.calories_burned
            if exercise.calories_burned > 0
            else (
                (exercise.duration_minutes or 0)
                * exercise.calories_burned_per_minute
            )
            for exercise in exercises
        )
    )

    return DailySummary(
        user_id=user_id,
        date=summary_date,
        calories_in=calories_in,
        calories_out=calories_out,
        net_calories=calories_in - calories_out,
    )


def calculate_daily_summary(
    session: Session,
    user_id: int,
    summary_date: date
) -> DailySummary:
    """
    Recompute a day's summary and persist it. Call this from write
    paths only (meal/exercise create, update, delete).
    """

    computed = compute_daily_summary_transient(
        session,
        user_id,
        summary_date
    )

    calories_in = computed.calories_in
    calories_out = computed.calories_out
    net_calories = computed.net_calories

    summary = session.exec(
        select(DailySummary).where(
            DailySummary.user_id == user_id,
            DailySummary.date == summary_date,
            DailySummary.deleted_at.is_(None)
        )
    ).first()

    if summary:

        summary.calories_in = calories_in
        summary.calories_out = calories_out
        summary.net_calories = net_calories

    else:

        summary = DailySummary(
            user_id=user_id,
            date=summary_date,
            calories_in=calories_in,
            calories_out=calories_out,
            net_calories=net_calories
        )

    session.add(summary)
    session.commit()
    session.refresh(summary)

    return summary


@router.get(
    "/{summary_date}",
    response_model=DailySummaryOut
)
def get_daily_summary(
    summary_date: date,
    session: SessionDep,
    current_user: CurrentUserDep
):

    # Read-only: never write from a GET. Prefer the cached row (kept
    # fresh by write paths); otherwise compute transiently.
    summary = session.exec(
        select(DailySummary).where(
            DailySummary.user_id == current_user.id,
            DailySummary.date == summary_date,
            DailySummary.deleted_at.is_(None)
        )
    ).first()

    if summary is None:
        summary = compute_daily_summary_transient(
            session,
            current_user.id,
            summary_date
        )

    return summary


@router.get(
    "",
    response_model=list[DailySummaryOut]
)
def get_daily_summaries(
    session: SessionDep,
    current_user: CurrentUserDep
):

    summaries = session.exec(
        select(DailySummary).where(
            DailySummary.user_id == current_user.id,
            DailySummary.deleted_at.is_(None)
        ).order_by(
            DailySummary.date.desc()
        )
    ).all()

    return summaries