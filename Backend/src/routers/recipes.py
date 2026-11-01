from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import FoodItem, FoodPortion, Recipe, RecipeIngredient
from src.routers.foods import check_user_food_name_unique, validate_per_100g_density
from src.schemas import (
    FoodPortionOut,
    RecipeCreate,
    RecipeIngredientOut,
    RecipeOut,
)
from src.services.food_access import visible_food, visible_portion
from src.services.food_service import FoodService

router = APIRouter(
    prefix="/recipes",
    tags=["Recipes"],
)


def _resolve_recipe_ingredients(
    session: SessionDep,
    user_id: int,
    data: RecipeCreate,
):
    food_ids = list({ing.food_id for ing in data.ingredients})
    foods = session.exec(
        select(FoodItem).where(
            FoodItem.id.in_(food_ids),
            *visible_food(user_id),
        )
    ).all()
    foods_by_id = {f.id: f for f in foods}

    if len(foods_by_id) != len(food_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more ingredient foods were not found.",
        )

    for f in foods:
        if f.kind == "recipe":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipes can't contain other recipes yet.",
            )

    service = FoodService(session=session, usda_client=None)  # type: ignore
    resolved: list[dict] = []
    total_grams = 0.0
    total_cal = 0.0
    total_pro = 0.0
    total_carb = 0.0
    total_fat = 0.0

    for ing in data.ingredients:
        food = foods_by_id[ing.food_id]
        try:
            gram_weight = service.resolve_gram_weight(
                food_id=food.id,
                quantity=ing.quantity,
                portion_id=ing.portion_id,
                unit=ing.unit,
                user_id=user_id,
            )
            nutrition = FoodService.calculate_nutrition_from_grams(
                food=food,
                gram_weight=gram_weight,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        portion = None
        if ing.portion_id:
            portion = service.get_food_portion_for_food(
                food_id=food.id,
                portion_id=ing.portion_id,
                user_id=user_id,
            )
        unit = portion.unit if portion else (ing.unit or "g")

        total_grams += gram_weight
        total_cal += nutrition["calories"]
        total_pro += nutrition["protein"]
        total_carb += nutrition["carbs"]
        total_fat += nutrition["fat"]

        resolved.append(
            {
                "food": food,
                "portion": portion,
                "quantity": ing.quantity,
                "unit": unit,
                "gram_weight": gram_weight,
                "nutrition": nutrition,
            }
        )

    cooked = data.cooked_weight_g if data.cooked_weight_g is not None else total_grams
    factor = 100.0 / cooked
    cal_100 = round(total_cal * factor, 2)
    pro_100 = round(total_pro * factor, 2)
    carb_100 = round(total_carb * factor, 2)
    fat_100 = round(total_fat * factor, 2)

    validate_per_100g_density(
        cal_100,
        pro_100,
        carb_100,
        fat_100,
        detail_prefix="Cooked weight looks too low",
    )

    return (
        resolved,
        round(total_grams, 2),
        round(cooked, 2),
        round(total_cal, 2),
        round(total_pro, 2),
        round(total_carb, 2),
        round(total_fat, 2),
        cal_100,
        pro_100,
        carb_100,
        fat_100,
    )


def _build_recipe_response(
    session: SessionDep,
    food: FoodItem,
    recipe: Recipe,
    user_id: int,
) -> RecipeOut:
    ing_rows = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.recipe_food_id == food.id)
    ).all()

    ing_food_ids = list({r.ingredient_food_id for r in ing_rows})
    ing_foods = (
        session.exec(select(FoodItem).where(FoodItem.id.in_(ing_food_ids))).all()
        if ing_food_ids
        else []
    )
    foods_by_id = {f.id: f for f in ing_foods}

    portion_ids = [r.portion_id for r in ing_rows if r.portion_id is not None]
    ing_portions = (
        session.exec(select(FoodPortion).where(FoodPortion.id.in_(portion_ids))).all()
        if portion_ids
        else []
    )
    portions_by_id = {p.id: p for p in ing_portions}

    ingredients_out: list[RecipeIngredientOut] = []
    total_grams = 0.0
    total_cal = 0.0
    total_pro = 0.0
    total_carb = 0.0
    total_fat = 0.0

    for row in ing_rows:
        ing_food = foods_by_id.get(row.ingredient_food_id)
        if ing_food is not None:
            nutrition = FoodService.calculate_nutrition_from_grams(
                food=ing_food,
                gram_weight=row.gram_weight,
            )
            food_name = ing_food.name
        else:
            nutrition = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
            food_name = "Unknown food"

        total_grams += row.gram_weight
        total_cal += nutrition["calories"]
        total_pro += nutrition["protein"]
        total_carb += nutrition["carbs"]
        total_fat += nutrition["fat"]

        portion = portions_by_id.get(row.portion_id) if row.portion_id else None
        ingredients_out.append(
            RecipeIngredientOut(
                id=row.id,
                food_id=row.ingredient_food_id,
                food_name=food_name,
                portion_id=row.portion_id,
                portion_name=portion.name if portion else None,
                quantity=row.quantity,
                unit=row.unit,
                gram_weight=row.gram_weight,
                calories=nutrition["calories"],
                protein=nutrition["protein"],
                carbs=nutrition["carbs"],
                fat=nutrition["fat"],
            )
        )

    cooked = (
        recipe.cooked_weight_g
        if recipe.cooked_weight_g is not None
        else total_grams
    )
    portion_grams = round(cooked / recipe.servings, 2) if recipe.servings > 0 else 0.0

    portions = session.exec(
        select(FoodPortion)
        .where(
            FoodPortion.food_id == food.id,
            visible_portion(user_id),
        )
        .order_by(FoodPortion.name)
    ).all()

    return RecipeOut(
        id=food.id,
        food_id=food.id,
        name=food.name,
        servings=recipe.servings,
        cooked_weight_g=recipe.cooked_weight_g,
        total_grams=round(total_grams, 2),
        cooked_grams=round(cooked, 2),
        portion_grams=portion_grams,
        total_calories=round(total_cal, 2),
        total_protein=round(total_pro, 2),
        total_carbs=round(total_carb, 2),
        total_fat=round(total_fat, 2),
        calories_per_portion=round(total_cal / recipe.servings, 2),
        protein_per_portion=round(total_pro / recipe.servings, 2),
        carbs_per_portion=round(total_carb / recipe.servings, 2),
        fat_per_portion=round(total_fat / recipe.servings, 2),
        calories_per_100g=food.calories_per_100g,
        protein_per_100g=food.protein_per_100g,
        carbs_per_100g=food.carbs_per_100g,
        fat_per_100g=food.fat_per_100g,
        portions=[FoodPortionOut.model_validate(p) for p in portions],
        ingredients=ingredients_out,
    )


@router.post(
    "",
    response_model=RecipeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_recipe(
    data: RecipeCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    check_user_food_name_unique(session, current_user.id, data.name)

    (
        resolved,
        _total_grams,
        cooked,
        _total_cal,
        _total_pro,
        _total_carb,
        _total_fat,
        cal_100,
        pro_100,
        carb_100,
        fat_100,
    ) = _resolve_recipe_ingredients(session, current_user.id, data)

    food = FoodItem(
        name=data.name,
        user_id=current_user.id,
        kind="recipe",
        calories_per_100g=cal_100,
        protein_per_100g=pro_100,
        carbs_per_100g=carb_100,
        fat_per_100g=fat_100,
        base_unit="g",
    )
    session.add(food)
    session.flush()

    recipe = Recipe(
        food_id=food.id,
        servings=data.servings,
        cooked_weight_g=data.cooked_weight_g,
    )
    session.add(recipe)

    for item in resolved:
        session.add(
            RecipeIngredient(
                recipe_food_id=food.id,
                ingredient_food_id=item["food"].id,
                portion_id=item["portion"].id if item["portion"] else None,
                quantity=item["quantity"],
                unit=item["unit"],
                gram_weight=item["gram_weight"],
            )
        )

    session.add(
        FoodPortion(
            food_id=food.id,
            name="1 portion",
            quantity=1.0,
            unit="portion",
            gram_weight=round(cooked / data.servings, 2),
        )
    )

    session.commit()
    session.refresh(food)
    session.refresh(recipe)
    return _build_recipe_response(session, food, recipe, current_user.id)


@router.get(
    "/{food_id}",
    response_model=RecipeOut,
)
def get_recipe(
    food_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    food = session.exec(
        select(FoodItem).where(
            FoodItem.id == food_id,
            FoodItem.user_id == current_user.id,
            FoodItem.kind == "recipe",
            FoodItem.deleted_at.is_(None),
        )
    ).first()
    if food is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )

    recipe = session.get(Recipe, food.id)
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )

    return _build_recipe_response(session, food, recipe, current_user.id)


@router.put(
    "/{food_id}",
    response_model=RecipeOut,
)
def update_recipe(
    food_id: int,
    data: RecipeCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    food = session.exec(
        select(FoodItem).where(
            FoodItem.id == food_id,
            FoodItem.user_id == current_user.id,
            FoodItem.kind == "recipe",
            FoodItem.deleted_at.is_(None),
        )
    ).first()
    if food is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )

    recipe = session.get(Recipe, food.id)
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )

    check_user_food_name_unique(
        session,
        current_user.id,
        data.name,
        exclude_food_id=food.id,
    )

    (
        resolved,
        _total_grams,
        cooked,
        _total_cal,
        _total_pro,
        _total_carb,
        _total_fat,
        cal_100,
        pro_100,
        carb_100,
        fat_100,
    ) = _resolve_recipe_ingredients(session, current_user.id, data)

    old_ings = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.recipe_food_id == food.id)
    ).all()
    for old_ing in old_ings:
        session.delete(old_ing)

    food.name = data.name
    food.calories_per_100g = cal_100
    food.protein_per_100g = pro_100
    food.carbs_per_100g = carb_100
    food.fat_per_100g = fat_100
    food.updated_at = datetime.now(timezone.utc)
    session.add(food)

    recipe.servings = data.servings
    recipe.cooked_weight_g = data.cooked_weight_g
    session.add(recipe)

    portion = session.exec(
        select(FoodPortion).where(
            FoodPortion.food_id == food.id,
            FoodPortion.user_id.is_(None),
        )
    ).first()
    if portion is not None:
        portion.gram_weight = round(cooked / data.servings, 2)
        session.add(portion)
    else:
        session.add(
            FoodPortion(
                food_id=food.id,
                name="1 portion",
                quantity=1.0,
                unit="portion",
                gram_weight=round(cooked / data.servings, 2),
            )
        )

    for item in resolved:
        session.add(
            RecipeIngredient(
                recipe_food_id=food.id,
                ingredient_food_id=item["food"].id,
                portion_id=item["portion"].id if item["portion"] else None,
                quantity=item["quantity"],
                unit=item["unit"],
                gram_weight=item["gram_weight"],
            )
        )

    session.commit()
    session.refresh(food)
    session.refresh(recipe)
    return _build_recipe_response(session, food, recipe, current_user.id)
