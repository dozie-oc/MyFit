"""
User goal CRUD router.

GET  /goals        - Return the current user's goal (or empty).
POST /goals        - Create or update the current user's goal (upsert).
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlmodel import select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import UserGoal
from src.schemas import UserGoalOut, UserGoalUpdate

router = APIRouter(prefix="/goals", tags=["Goals"])


@router.get("", response_model=UserGoalOut)
def get_goal(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> UserGoalOut:
    """Return the authenticated user's current fitness goal."""

    goal = session.exec(
        select(UserGoal).where(UserGoal.user_id == current_user.id)
    ).first()

    if goal is None:
        # Return empty defaults – no goal set yet.
        return UserGoalOut()

    return UserGoalOut.model_validate(goal)


@router.post("", response_model=UserGoalOut)
def upsert_goal(
    data: UserGoalUpdate,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> UserGoalOut:
    """Create or update the authenticated user's fitness goal."""

    goal = session.exec(
        select(UserGoal).where(UserGoal.user_id == current_user.id)
    ).first()

    if goal is None:
        goal = UserGoal(user_id=current_user.id)
        session.add(goal)

    # Apply only the fields that were supplied (non-None in the payload).
    update_data = data.model_dump(exclude_unset=False)
    for field, value in update_data.items():
        setattr(goal, field, value)

    goal.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(goal)

    return UserGoalOut.model_validate(goal)
