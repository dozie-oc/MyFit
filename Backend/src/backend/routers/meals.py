from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Meal, MealItem
from ..schemas import MealCreate, MealOut

router = APIRouter(
    prefix="/meals",    
    tags=["meals"],
)

@router.post("/", response_model=MealOut)
def create_meal(meal_data: MealCreate, session: Session = Depends(get_session)):
    """Create a new meal entry in the database."""
    total_calories = sum(item.calories for item in meal_data.items)

    meal = Meal(
        user_id=1,
        calories=total_calories
    )

    session.add(meal)
    session.flush() #to assign ids

    # then to create the meal
    for item in meal_data.items:
        meal_item = Meal(
            meal_id = meal.id,
            quantity = item.quantity,
            units = item.unit,
            calories=item.calories
        )

        session.add(meal_item)

    session.commit()
    session.refresh(meal)

    return meal