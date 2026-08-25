from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime

from ..database import get_session
from ..models import Meal, MealItem, FoodItem
from ..schemas import MealCreate, MealOut

router = APIRouter(
    prefix="/meals",    
    tags=["meals"],
)

@router.post("/", response_model=MealOut)
def create_meal(meal_data: MealCreate, session: Session = Depends(get_session)):
    """Create a new meal entry in the database."""
    total_calories = 0

    # Find foods submitted to calculate calories
    for item in meal_data.food_items:
        food = session.get(FoodItem, item.food_id)

        if food is None:
            raise HTTPException(
                status_code=404,
                detail=f"Food item {item.food_id}"
            )

        total_calories +=(
        food.calories_per_unit * item.quantity
        )

        # Create the meal
        meal = Meal(
            user_id=1, #temporary
            date=meal_data.date,
            calories=round(total_calories)
        )

        session.add(meal)
        session.flush() # To create the meal.id

        #create the mealitems
        for item in meal_data.food_items:
            meal_item = MealItem(
                meal_id=meal.id,
                food_id=item.food_id,
                quantity=item.quantity
            )

            session.add(meal_item)


        session.commit()
        session.refresh(meal)

        return meal