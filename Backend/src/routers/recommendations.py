"""
Recommendation router.

GET /recommendations/today
    Returns the single most relevant recommendation for the authenticated
    user based on their goal and what they have already logged today.
"""

from fastapi import APIRouter

from src.dependencies import CurrentUserDep, SessionDep
from src.schemas import RecommendationResponse
from src.services.recommendation_service import get_recommendation

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/today", response_model=RecommendationResponse)
def today_recommendation(
    current_user: CurrentUserDep,
    session: SessionDep,
    type: str | None = None,
) -> RecommendationResponse:
    """
    Return a contextual recommendation for the authenticated user.

    The recommendation is based on:
    - The user's active fitness goal and profile
    - Today's logged meals and nutrition totals
    - Today's logged exercises

    Query parameter `type`:
    - 'exercise': Force an exercise recommendation
    - 'meal': Force a meal recommendation
    - null: Automatic smart recommendation

    Returns has_recommendation=False if no useful recommendation exists.
    """

    return get_recommendation(session=session, user=current_user, rec_type=type)
