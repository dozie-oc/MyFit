from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import FoodItem
from ..schemas import FoodItemOut

router = APIRouter(
    prefix="/foods",
    tags=["foods"],
)

@router.get("/", response_model=list[FoodItemOut])
def get_food_items(session: Session = Depends(get_session)):
    """Retrieve all food items from the database."""
    food_items = session.exec(select(FoodItem)).all()
    return food_items