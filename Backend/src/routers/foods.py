from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlmodel import select

from src.config import settings
from src.dependencies import CurrentUserDep, SessionDep
from src.models import FoodItem, FoodPortion
from src.schemas import (
    CustomFoodCreate,
    CustomFoodUpdate,
    FoodItemOut,
    FoodPortionOut,
    FoodSearchResult,
    PersonalPortionCreate,
)
from src.services.food_access import visible_food, visible_portion
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


def build_food_responses(
    session: SessionDep,
    foods: list[FoodItem],
    user_id: int | None = None,
) -> list[FoodItemOut]:
    """
    Build API representations for many FoodItems using a single
    portions query (instead of one query per food).

    FoodItem does not define a SQLModel relationship to FoodPortion,
    so portions are fetched explicitly and grouped by food id.
    """

    if not foods:
        return []

    portion_conds = [FoodPortion.food_id.in_([f.id for f in foods])]
    if user_id is not None:
        portion_conds.append(visible_portion(user_id))
    else:
        portion_conds.append(FoodPortion.user_id.is_(None))

    portions = session.exec(
        select(FoodPortion)
        .where(*portion_conds)
        .order_by(FoodPortion.name)
    ).all()

    portions_by_food: dict[int, list[FoodPortion]] = {}
    for portion in portions:
        portions_by_food.setdefault(portion.food_id, []).append(portion)

    return [
        FoodItemOut(
            id=food.id,
            name=food.name,
            usda_fdc_id=food.usda_fdc_id,
            usda_data_type=food.usda_data_type,
            calories_per_100g=food.calories_per_100g,
            protein_per_100g=food.protein_per_100g,
            carbs_per_100g=food.carbs_per_100g,
            fat_per_100g=food.fat_per_100g,
            base_unit=food.base_unit,
            kind=food.kind,
            portions=[
                FoodPortionOut.model_validate(portion)
                for portion in portions_by_food.get(food.id, [])
            ],
        )
        for food in foods
    ]


def build_food_response(
    session: SessionDep,
    food: FoodItem,
    user_id: int | None = None,
) -> FoodItemOut:
    """Build the API representation of a single FoodItem."""

    return build_food_responses(session, [food], user_id=user_id)[0]


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
        .where(*visible_food(current_user.id))
        .order_by(FoodItem.name)
        .offset(offset)
        .limit(limit)
    )

    foods = session.exec(
        statement
    ).all()

    return build_food_responses(session, foods, user_id=current_user.id)


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
            *visible_food(current_user.id),
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

    return build_food_responses(session, foods, user_id=current_user.id)


def validate_per_100g_density(
    calories_per_100g: float,
    protein_per_100g: float,
    carbs_per_100g: float,
    fat_per_100g: float,
    detail_prefix: str = "Invalid nutrition per 100g",
) -> None:
    if calories_per_100g > 900:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{detail_prefix}: calories per 100g cannot exceed 900 kcal.",
        )
    if protein_per_100g + carbs_per_100g + fat_per_100g > 100.5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{detail_prefix}: protein + carbs + fat cannot exceed 100g per 100g.",
        )


def check_user_food_name_unique(
    session: SessionDep,
    user_id: int,
    name: str,
    exclude_food_id: int | None = None,
) -> None:
    conds = [
        FoodItem.user_id == user_id,
        FoodItem.deleted_at.is_(None),
        FoodItem.kind.in_(("custom", "recipe")),
        func.lower(FoodItem.name) == name.strip().lower(),
    ]
    if exclude_food_id is not None:
        conds.append(FoodItem.id != exclude_food_id)
    dup = session.exec(select(FoodItem).where(*conds)).first()
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a custom food or recipe with that name.",
        )


@router.post(
    "/custom",
    response_model=FoodItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_food(
    data: CustomFoodCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    check_user_food_name_unique(session, current_user.id, data.name)

    factor = (100.0 / data.serving_grams) if data.basis == "serving" else 1.0
    cal_100 = data.calories * factor
    pro_100 = data.protein * factor
    carb_100 = data.carbs * factor
    fat_100 = data.fat * factor

    validate_per_100g_density(cal_100, pro_100, carb_100, fat_100)

    food = FoodItem(
        name=data.name,
        user_id=current_user.id,
        kind="custom",
        calories_per_100g=cal_100,
        protein_per_100g=pro_100,
        carbs_per_100g=carb_100,
        fat_per_100g=fat_100,
        base_unit="g",
    )
    session.add(food)
    session.flush()

    if data.basis == "serving":
        portion = FoodPortion(
            food_id=food.id,
            name=f"1 {data.serving_name}",
            quantity=1.0,
            unit=data.serving_name,
            gram_weight=data.serving_grams,
        )
        session.add(portion)

    session.commit()
    session.refresh(food)
    return build_food_response(session, food, user_id=current_user.id)


@router.patch(
    "/custom/{food_id}",
    response_model=FoodItemOut,
)
def update_custom_food(
    food_id: int,
    data: CustomFoodUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    food = session.exec(
        select(FoodItem).where(
            FoodItem.id == food_id,
            FoodItem.user_id == current_user.id,
            FoodItem.kind == "custom",
            FoodItem.deleted_at.is_(None),
        )
    ).first()
    if food is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom food not found.",
        )

    if data.name is not None:
        check_user_food_name_unique(
            session, current_user.id, data.name, exclude_food_id=food.id
        )
        food.name = data.name

    serving_portion = session.exec(
        select(FoodPortion).where(
            FoodPortion.food_id == food.id,
            FoodPortion.user_id.is_(None),
        )
    ).first()

    if data.basis is not None:
        basis = data.basis
    elif data.serving_grams is not None:
        basis = "serving"
    elif serving_portion is not None:
        basis = "serving"
    else:
        basis = "per_100g"

    sg = (
        data.serving_grams
        if data.serving_grams is not None
        else (serving_portion.gram_weight if serving_portion else 100.0)
    )
    factor = (100.0 / sg) if basis == "serving" else 1.0

    cal_100 = (
        data.calories * factor
        if data.calories is not None
        else food.calories_per_100g
    )
    pro_100 = (
        data.protein * factor
        if data.protein is not None
        else food.protein_per_100g
    )
    carb_100 = (
        data.carbs * factor if data.carbs is not None else food.carbs_per_100g
    )
    fat_100 = data.fat * factor if data.fat is not None else food.fat_per_100g

    validate_per_100g_density(cal_100, pro_100, carb_100, fat_100)

    food.calories_per_100g = cal_100
    food.protein_per_100g = pro_100
    food.carbs_per_100g = carb_100
    food.fat_per_100g = fat_100
    food.updated_at = datetime.now(timezone.utc)
    session.add(food)

    if data.serving_grams is not None or data.serving_name is not None or data.basis == "serving":
        sname = (
            data.serving_name
            if data.serving_name is not None
            else (serving_portion.unit if serving_portion else "serving")
        )
        if serving_portion is not None:
            if data.serving_grams is not None:
                serving_portion.gram_weight = data.serving_grams
            if data.serving_name is not None:
                serving_portion.name = f"1 {sname}"
                serving_portion.unit = sname
            session.add(serving_portion)
        elif basis == "serving":
            session.add(
                FoodPortion(
                    food_id=food.id,
                    name=f"1 {sname}",
                    quantity=1.0,
                    unit=sname,
                    gram_weight=sg,
                )
            )

    session.commit()
    session.refresh(food)
    return build_food_response(session, food, user_id=current_user.id)


@router.delete(
    "/custom/{food_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_custom_food(
    food_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    food = session.exec(
        select(FoodItem).where(
            FoodItem.id == food_id,
            FoodItem.user_id == current_user.id,
            FoodItem.kind.in_(("custom", "recipe")),
            FoodItem.deleted_at.is_(None),
        )
    ).first()
    if food is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom food not found.",
        )

    food.deleted_at = datetime.now(timezone.utc)
    session.add(food)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{food_id}/portions",
    response_model=FoodPortionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_personal_portion(
    food_id: int,
    data: PersonalPortionCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    food = session.exec(
        select(FoodItem).where(
            FoodItem.id == food_id,
            *visible_food(current_user.id),
        )
    ).first()
    if food is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food item not found.",
        )

    dup = session.exec(
        select(FoodPortion).where(
            FoodPortion.food_id == food_id,
            FoodPortion.user_id == current_user.id,
            func.lower(FoodPortion.name) == data.name.lower(),
        )
    ).first()
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a portion with that name for this food.",
        )

    portion = FoodPortion(
        food_id=food_id,
        user_id=current_user.id,
        name=data.name,
        quantity=data.quantity,
        unit="portion",
        gram_weight=data.grams,
    )
    session.add(portion)
    session.commit()
    session.refresh(portion)
    return FoodPortionOut.model_validate(portion)


@router.delete(
    "/portions/{portion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_personal_portion(
    portion_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    portion = session.exec(
        select(FoodPortion).where(
            FoodPortion.id == portion_id,
            FoodPortion.user_id == current_user.id,
        )
    ).first()
    if portion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portion not found.",
        )

    session.delete(portion)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
            *visible_food(current_user.id),
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
        user_id=current_user.id,
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