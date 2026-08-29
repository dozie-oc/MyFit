from datetime import date, datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from backend.dependencies import CurrentUserDep, SessionDep
from backend.models import Meal, MealItem
from backend.schemas import (
    MealCaloriesOverride,
    MealCreate,
    MealItemOut,
    MealOut,
)

from backend.routers.daily_summary import calculate_daily_summary


router = APIRouter(
    prefix="/meals",
    tags=["Meals"]
)


def build_meal_response(
    session: SessionDep,
    meal: Meal
) -> MealOut:

    items = session.exec(
        select(MealItem).where(
            MealItem.meal_id == meal.id,
            MealItem.deleted_at.is_(None)
        )
    ).all()

    return MealOut(
        id=meal.id,
        date=meal.date,
        calories=meal.calories,
        created_at=meal.created_at,
        items=[
            MealItemOut.model_validate(item)
            for item in items
        ]
    )


@router.post(
    "",
    response_model=MealOut,
    status_code=status.HTTP_201_CREATED
)
def create_meal(
    meal_data: MealCreate,
    session: SessionDep,
    current_user: CurrentUserDep
):

    total_calories = sum(
        item.calories
        for item in meal_data.items
    )

    meal = Meal(
        user_id=current_user.id,
        date=meal_data.date,
        calories=total_calories
    )

    session.add(meal)
    session.flush()

    for item_data in meal_data.items:

        meal_item = MealItem(
            meal_id=meal.id,
            quantity=item_data.quantity,
            unit=item_data.unit,
            calories=item_data.calories
        )

        session.add(meal_item)

    session.commit()
    session.refresh(meal)

    calculate_daily_summary(
        session,
        current_user.id,
        meal.date
    )

    return build_meal_response(
        session,
        meal
    )


@router.get(
    "",
    response_model=list[MealOut]
)
def get_meals(
    session: SessionDep,
    current_user: CurrentUserDep,
    meal_date: date | None = None
):

    statement = select(Meal).where(
        Meal.user_id == current_user.id,
        Meal.deleted_at.is_(None)
    )

    if meal_date:
        statement = statement.where(
            Meal.date == meal_date
        )

    statement = statement.order_by(
        Meal.date.desc(),
        Meal.created_at.desc()
    )

    meals = session.exec(statement).all()

    return [
        build_meal_response(session, meal)
        for meal in meals
    ]


@router.get(
    "/{meal_id}",
    response_model=MealOut
)
def get_meal(
    meal_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):

    meal = session.exec(
        select(Meal).where(
            Meal.id == meal_id,
            Meal.user_id == current_user.id,
            Meal.deleted_at.is_(None)
        )
    ).first()

    if not meal:
        raise HTTPException(
            status_code=404,
            detail="Meal not found"
        )

    return build_meal_response(
        session,
        meal
    )


@router.patch(
    "/{meal_id}/calories",
    response_model=MealOut
)
def override_meal_calories(
    meal_id: int,
    data: MealCaloriesOverride,
    session: SessionDep,
    current_user: CurrentUserDep
):

    meal = session.exec(
        select(Meal).where(
            Meal.id == meal_id,
            Meal.user_id == current_user.id,
            Meal.deleted_at.is_(None)
        )
    ).first()

    if not meal:
        raise HTTPException(
            status_code=404,
            detail="Meal not found"
        )

    meal.calories = data.override_calories

    session.add(meal)
    session.commit()
    session.refresh(meal)

    calculate_daily_summary(
        session,
        current_user.id,
        meal.date
    )

    return build_meal_response(
        session,
        meal
    )


@router.delete(
    "/{meal_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_meal(
    meal_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):

    meal = session.exec(
        select(Meal).where(
            Meal.id == meal_id,
            Meal.user_id == current_user.id,
            Meal.deleted_at.is_(None)
        )
    ).first()

    if not meal:
        raise HTTPException(
            status_code=404,
            detail="Meal not found"
        )

    meal_date = meal.date

    meal.deleted_at = datetime.utcnow()

    session.add(meal)
    session.commit()

    calculate_daily_summary(
        session,
        current_user.id,
        meal_date
    )

    return None