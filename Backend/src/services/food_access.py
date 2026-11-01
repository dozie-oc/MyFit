from sqlalchemy import or_

from src.models import FoodItem, FoodPortion


def visible_food(user_id: int, include_hidden: bool = False) -> list:
    """WHERE conditions for foods a user may see: shared catalog + their own."""
    conds = [
        FoodItem.deleted_at.is_(None),
        or_(FoodItem.user_id.is_(None), FoodItem.user_id == user_id),
    ]
    if not include_hidden:
        conds.append(FoodItem.kind != "quick")
    return conds


def visible_portion(user_id: int):
    return or_(FoodPortion.user_id.is_(None), FoodPortion.user_id == user_id)

