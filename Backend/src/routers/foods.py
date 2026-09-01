from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from src.config import settings
from src.dependencies import CurrentUserDep, SessionDep
from src.models import FoodItem, FoodPortion
from src.schemas import (
    FoodItemOut,
    FoodPortionOut,
    FoodSearchResult,
    FoodSearchResponse,
)
from src.services.food_service import FoodService
from src.services.usda_client import (
    USDAAPIError,
    USDAClient,
)


router = APIRouter(
    prefix="/foods",
    tags=["Foods"],
)


# ============================================================
# HELPERS
# ============================================================


def build_food_response(
    session: SessionDep,
    food: FoodItem,
) -> FoodItemOut:
    """
    Build the API representation of a FoodItem.

    FoodItem does not currently define a SQLModel relationship to
    FoodPortion, so portions are retrieved explicitly.

    Keeping this here gives us a single place to construct the
    response instead of duplicating the portion query across
    multiple endpoints.
    """

    portions = session.exec(
        select(FoodPortion)
        .where(
            FoodPortion.food_id == food.id
        )
        .order_by(FoodPortion.name)
    ).all()

    return FoodItemOut(
        id=food.id,
        name=food.name,
        usda_fdc_id=food.usda_fdc_id,
        usda_data_type=food.usda_data_type,
        calories_per_100g=food.calories_per_100g,
        protein_per_100g=food.protein_per_100g,
        carbs_per_100g=food.carbs_per_100g,
        fat_per_100g=food.fat_per_100g,
        base_unit=food.base_unit,
        portions=[
            FoodPortionOut.model_validate(
                portion
            )
            for portion in portions
        ],
    )


# ============================================================
# LOCAL FOOD CATALOGUE
# ============================================================


@router.get(
    "",
    response_model=list[FoodItemOut],
)
def get_foods(
    session: SessionDep,
    current_user: CurrentUserDep,
    offset: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
):
    """
    Return foods from the local catalogue.

    Pagination prevents the entire food catalogue from being
    returned in a single response.

    Authentication is required because the food catalogue is part
    of the application's authenticated API.
    """

    statement = (
        select(FoodItem)
        .where(
            FoodItem.deleted_at.is_(None)
        )
        .order_by(FoodItem.name)
        .offset(offset)
        .limit(limit)
    )

    foods = session.exec(
        statement
    ).all()

    return [
        build_food_response(
            session,
            food,
        )
        for food in foods
    ]


@router.get(
    "/search",
    response_model=list[FoodItemOut],
)
def search_local_foods(
    session: SessionDep,
    current_user: CurrentUserDep,
    q: str = Query(
        min_length=1,
        max_length=100,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=50,
    ),
):
    """
    Search foods already stored in the local catalogue.

    This endpoint deliberately does NOT call USDA.

    Meal logging should depend only on our local database so that
    an external API outage cannot prevent users from logging food.
    """

    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty.",
        )

    statement = (
        select(FoodItem)
        .where(
            FoodItem.deleted_at.is_(None),
            FoodItem.name.ilike(
                f"%{query}%"
            ),
        )
        .order_by(FoodItem.name)
        .limit(limit)
    )

    foods = session.exec(
        statement
    ).all()

    return [
        build_food_response(
            session,
            food,
        )
        for food in foods
    ]


@router.get(
    "/{food_id}",
    response_model=FoodItemOut,
)
def get_food(
    food_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Retrieve a single food item from the local catalogue.
    """

    food = session.exec(
        select(FoodItem)
        .where(
            FoodItem.id == food_id,
            FoodItem.deleted_at.is_(None),
        )
    ).first()

    if food is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food item not found.",
        )

    return build_food_response(
        session,
        food,
    )


# ============================================================
# USDA FOOD SEARCH
# ============================================================


@router.get(
    "/usda/search",
    response_model=list[FoodSearchResult],
)
async def search_usda_foods(
    current_user: CurrentUserDep,
    q: str = Query(
        min_length=2,
        max_length=100,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=25,
        ge=1,
        le=50,
    ),
):
    """
    Search USDA FoodData Central.

    This does NOT automatically import the returned foods.

    Intended client flow:

        1. User searches for "banana".
        2. USDA results are displayed.
        3. User selects a food.
        4. Client imports the selected food.
        5. The food becomes part of our local catalogue.

    This prevents us from filling our database with every USDA
    search result a user happens to look at.
    """

    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty.",
        )

    try:
        async with USDAClient(settings) as usda_client:

            service = FoodService(
                session=None,  # type: ignore
                usda_client=usda_client,
            )

            results, total_hits = (
                await service.search_foods(
                    query,
                    page_size=page_size,
                    page_number=page,
                )
            )

            return results

    except USDAAPIError as exc:


        if exc.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="USDA food service authentication failed.",
            ) from exc

        if exc.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="USDA food service access was denied.",
            ) from exc

        if exc.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "USDA food service is temporarily rate "
                    "limited. Please try again later."
                ),
            ) from exc

        if exc.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "USDA food service is currently unavailable. "
                    "Please try again later."
                ),
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Unable to retrieve food data from "
                "USDA FoodData Central."
            ),
        ) from exc


# ============================================================
# USDA FOOD IMPORT
# ============================================================


@router.post(
    "/import/{fdc_id}",
    response_model=FoodItemOut,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/usda/{fdc_id}/import",
    response_model=FoodItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def import_usda_food(
    fdc_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Import a specific USDA food into the local catalogue.

    The USDA FDC ID is used rather than allowing the client to
    submit nutrition information.

    Flow:

        Client
            ↓
        USDA food ID
            ↓
        USDA
            ↓
        our backend
            ↓
        normalized FoodItem
            ↓
        database

    The client never gets to decide the canonical calories or
    macronutrients stored for the food.
    """

    if fdc_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="USDA FDC ID must be greater than zero.",
        )

    try:
        async with USDAClient(settings) as usda_client:

            service = FoodService(
                session=session,
                usda_client=usda_client,
            )

            food = await service.import_usda_food(
                fdc_id
            )

            # FoodService deliberately does not commit.
            #
            # The router owns the transaction boundary for this
            # endpoint.
            session.commit()
            session.refresh(food)

            return build_food_response(
                session,
                food,
            )

    except USDAAPIError as exc:

        session.rollback()

        if exc.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="USDA food service authentication failed.",
            ) from exc

        if exc.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="USDA food service access was denied.",
            ) from exc

        if exc.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="USDA food not found.",
            ) from exc

        if exc.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "USDA food service is temporarily rate "
                    "limited. Please try again later."
                ),
            ) from exc

        if exc.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "USDA food service is currently unavailable. "
                    "Please try again later."
                ),
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Unable to retrieve food data from "
                "USDA FoodData Central."
            ),
        ) from exc

    except ValueError as exc:

        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to import food.",
        ) from exc