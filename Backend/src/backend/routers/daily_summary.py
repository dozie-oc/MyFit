from datetime import date

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from backend.dependencies import CurrentUserDep, SessionDep
from backend.models import (
    DailySummary,
    Exercise,
    Meal,
)
from backend.schemas import DailySummaryOut


router = APIRouter(
    prefix="/summary",
    tags=["Daily Summary"]
)


def calculate_daily_summary(
    session: Session,
    user_id: int,
    summary_date: date
) -> DailySummary:

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
            (
                exercise.duration_minutes or 0
            )
            * exercise.calories_burned_per_minute
            for exercise in exercises
        )
    )

    net_calories = (
        calories_in
        - calories_out
    )

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

    summary = calculate_daily_summary(
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