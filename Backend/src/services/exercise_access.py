from sqlalchemy import or_
from src.models import ExerciseCatalogItem


def visible_exercise(user_id: int) -> list:
    """Standard catalog items plus this user's own custom ones."""
    return [
        ExerciseCatalogItem.deleted_at.is_(None),
        or_(
            ExerciseCatalogItem.is_custom == False,  # noqa: E712
            ExerciseCatalogItem.user_id == user_id,
        ),
    ]

