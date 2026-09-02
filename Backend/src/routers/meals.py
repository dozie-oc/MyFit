from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import FoodItem, Meal, MealItem
from src.schemas import (
    MealCaloriesOverride,
    MealCreate,
    MealItemOut,
    MealOut,
)
from src.routers.daily_summary import calculate_daily_summary
from src.services.food_service import FoodService


router = APIRouter(
    prefix="/meals",
    tags=["Meals"]
)


def build_meal_response(
    session: Session,
    meal: Meal
) -> MealOut:
    """
    Build the API response for a meal including its items and food names.

    MealItem stores nutritional snapshots, and we resolve human-readable
    food and portion names for the client display.
    """

    items = session.exec(
        select(MealItem).where(
            MealItem.meal_id == meal.id,
            MealItem.deleted_at.is_(None)
        )
    ).all()

    food_ids = {item.food_id for item in items}
    portion_ids = {item.portion_id for item in items if item.portion_id is not None}

    foods: dict[int, str] = {}
    if food_ids:
        foods_list = session.exec(
            select(FoodItem).where(FoodItem.id.in_(food_ids))
        ).all()
        foods = {f.id: f.name for f in foods_list}

    portions: dict[int, str] = {}
    if portion_ids:
        from src.models import FoodPortion
        portions_list = session.exec(
            select(FoodPortion).where(FoodPortion.id.in_(portion_ids))
        ).all()
        portions = {p.id: p.name for p in portions_list}

    out_items: list[MealItemOut] = []
    for item in items:
        item_dict = item.model_dump()
        item_dict["food_name"] = foods.get(item.food_id, f"Food #{item.food_id}")
        item_dict["portion_name"] = portions.get(item.portion_id) if item.portion_id else None
        out_items.append(MealItemOut.model_validate(item_dict))

    return MealOut(
        id=meal.id,
        date=meal.date,
        calories=meal.calories,
        protein=meal.protein,
        carbs=meal.carbs,
        fat=meal.fat,
        created_at=meal.created_at,
        items=out_items
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
    """
    Create a meal using FoodItems from the local catalogue.

    The client supplies:
        food_id + quantity (+ optional portion_id or unit)

    The backend determines:
        gram_weight
        calories
        protein
        carbs
        fat

    Everything is committed as one transaction. If any food_id is
    invalid, no partial Meal or MealItem records are created.
    """

    food_ids = [
        item.food_id
        for item in meal_data.items
    ]

    # Remove duplicates before querying the database.
    unique_food_ids = set(food_ids)

    foods = session.exec(
        select(FoodItem).where(
            FoodItem.id.in_(unique_food_ids),
            FoodItem.deleted_at.is_(None)
        )
    ).all()

    foods_by_id = {
        food.id: food
        for food in foods
    }

    # Validate every requested food before creating anything.
    missing_food_ids = (
        unique_food_ids
        - foods_by_id.keys()
    )

    if missing_food_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "One or more food items were not found.",
                "food_ids": list(missing_food_ids)
            }
        )

    total_calories = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    meal = Meal(
        user_id=current_user.id,
        date=meal_data.date,
        calories=0,
        protein=0,
        carbs=0,
        fat=0
    )

    session.add(meal)
    session.flush()

    food_service = FoodService(session=session, usda_client=None)  # type: ignore

    for item_data in meal_data.items:

        food = foods_by_id[item_data.food_id]

        try:
            gram_weight = food_service.resolve_gram_weight(
                food_id=food.id,
                quantity=item_data.quantity,
                portion_id=item_data.portion_id,
                unit=item_data.unit,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        nutrition = FoodService.calculate_nutrition_from_grams(
            food=food,
            gram_weight=gram_weight,
        )

        calories = nutrition["calories"]
        protein = nutrition["protein"]
        carbs = nutrition["carbs"]
        fat = nutrition["fat"]

        total_calories += calories
        total_protein += protein
        total_carbs += carbs
        total_fat += fat

        portion = None
        if item_data.portion_id:
            portion = food_service.get_food_portion_for_food(
                food_id=food.id,
                portion_id=item_data.portion_id,
            )

        unit = portion.unit if portion else (item_data.unit or "g")

        meal_item = MealItem(
            meal_id=meal.id,
            food_id=food.id,
            portion_id=item_data.portion_id,
            quantity=item_data.quantity,
            unit=unit,
            gram_weight=gram_weight,
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
        )

        session.add(meal_item)

    meal.calories = total_calories
    meal.protein = total_protein
    meal.carbs = total_carbs
    meal.fat = total_fat

    session.add(meal)
    session.commit()
    session.refresh(meal)

    # The summary is recalculated only after the meal transaction
    # succeeds, preventing a summary from reflecting a meal that
    # failed to be created.
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
    """
    Return the authenticated user's meals.

    A date can optionally be supplied to retrieve only meals for
    a particular day.
    """

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
        build_meal_response(
            session,
            meal
        )
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
    """
    Allow the user to override the calculated calorie total.

    This is intentionally limited to calories for now. The underlying
    item-level nutritional calculation remains intact.
    """

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
    """
    Soft-delete a meal.

    The MealItems are retained because they belong to historical
    data, but they are excluded from normal queries through the
    meal's deleted state.
    """

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

    meal.deleted_at = datetime.now(timezone.utc)

    session.add(meal)
    session.commit()

    calculate_daily_summary(
        session,
        current_user.id,
        meal_date
    )

    return None