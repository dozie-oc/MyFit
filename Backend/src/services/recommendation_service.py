"""
Deterministic recommendation engine.

Gathers the user's goal, profile, today's meals, today's nutrition totals,
and today's exercises, then returns a single actionable recommendation
(or a no-recommendation response when nothing useful can be suggested).

No LLM, no ML model. Pure deterministic rule-based logic.
"""

from datetime import date as Date, timedelta
import zlib
from sqlalchemy import and_, func, or_
from sqlmodel import Session, select

from src.models import (
    Exercise,
    ExerciseCatalogItem,
    FoodItem,
    Meal,
    User,
    UserGoal,
    WorkoutSession,
)
from src.schemas import RecommendationItem, RecommendationResponse
from src.services.exercise_access import visible_exercise
from src.services.food_access import _word_in_text, matches_avoid, parse_avoid_terms


# ──────────────────────────────────────────────────────────────────────
# CONSTANTS & MAPPINGS
# ──────────────────────────────────────────────────────────────────────

# Multipliers for estimated daily maintenance calories by activity level (kcal per kg bodyweight)
ACTIVITY_CALORIE_MULTIPLIERS: dict[str, float] = {
    "sedentary": 30.0,
    "lightly_active": 32.0,
    "moderately_active": 35.0,
    "very_active": 38.0,
    "extremely_active": 42.0,
}

# Calorie delta (relative to maintenance) by goal
GOAL_CALORIE_DELTAS: dict[str, int] = {
    "lose_weight": -450,
    "gain_weight": 400,
    "build_muscle": 350,
    "get_stronger": 250,
    "improve_endurance": 200,
    "maintain_weight": 0,
    "improve_fitness": 0,
}

# Protein target (grams per kg bodyweight) by goal
GOAL_PROTEIN_PER_KG: dict[str, float] = {
    "lose_weight": 2.0,
    "build_muscle": 2.0,
    "gain_weight": 1.9,
    "get_stronger": 1.8,
    "improve_fitness": 1.5,
    "improve_endurance": 1.5,
    "maintain_weight": 1.4,
}

# Minimum remaining calories worth recommending a major meal for
MIN_CALORIE_REMAINING = 180

# Exercise categories to favour by goal
GOAL_EXERCISE_CATEGORY: dict[str, list[str]] = {
    "lose_weight": ["cardio", "strength"],
    "gain_weight": ["strength"],
    "build_muscle": ["strength"],
    "maintain_weight": ["cardio", "strength"],
    "improve_fitness": ["cardio", "strength", "flexibility"],
    "improve_endurance": ["cardio"],
    "get_stronger": ["strength"],
}

# Dietary classification keywords
MEAT_POULTRY_KEYWORDS: set[str] = {
    "chicken", "beef", "pork", "turkey", "bacon", "steak", "lamb", "duck",
    "sausage", "ham", "veal", "meat"
}
SEAFOOD_KEYWORDS: set[str] = {
    "fish", "salmon", "tuna", "shrimp", "seafood", "cod", "tilapia",
    "trout", "crab", "lobster", "sardine", "mackerel"
}
DAIRY_EGG_KEYWORDS: set[str] = {
    "egg", "yogurt", "milk", "cheese", "butter", "whey", "cream",
    "casein", "mayonnaise"
}


# ──────────────────────────────────────────────────────────────────────
# NUTRITION & TARGET HELPERS
# ──────────────────────────────────────────────────────────────────────

def _calculate_targets(user: User, goal: UserGoal | None) -> tuple[int, int]:
    """Calculate daily calorie and protein targets based on goal, weight, and activity level."""
    weight_kg = user.weight or 70.0
    weight_kg = max(40.0, min(weight_kg, 200.0))

    activity = (goal.activity_level or "moderately_active").lower() if goal else "moderately_active"
    multiplier = ACTIVITY_CALORIE_MULTIPLIERS.get(activity, 35.0)
    maintenance_calories = weight_kg * multiplier

    goal_type = (goal.goal_type or "maintain_weight").lower() if goal else "maintain_weight"
    delta = GOAL_CALORIE_DELTAS.get(goal_type, 0)
    calorie_target = int(max(1200, maintenance_calories + delta))

    protein_factor = GOAL_PROTEIN_PER_KG.get(goal_type, 1.5)
    protein_target = int(max(50, weight_kg * protein_factor))

    return calorie_target, protein_target


def _nutrition_per_grams(food: FoodItem, grams: float) -> dict[str, float]:
    factor = grams / 100.0
    return {
        "calories": round(food.calories_per_100g * factor, 1),
        "protein": round(food.protein_per_100g * factor, 1),
        "carbs": round(food.carbs_per_100g * factor, 1),
        "fat": round(food.fat_per_100g * factor, 1),
    }


def _is_food_allowed(food_name: str, dietary_pref: str, avoid_list: list[str]) -> bool:
    lower = food_name.lower()
    if matches_avoid(lower, avoid_list):
        return False

    if dietary_pref == "vegan":
        animal_keywords = MEAT_POULTRY_KEYWORDS | SEAFOOD_KEYWORDS | DAIRY_EGG_KEYWORDS
        if any(_word_in_text(kw, lower) for kw in animal_keywords):
            return False
    elif dietary_pref == "vegetarian":
        meat_fish = MEAT_POULTRY_KEYWORDS | SEAFOOD_KEYWORDS
        if any(_word_in_text(kw, lower) for kw in meat_fish):
            return False
    elif dietary_pref == "pescatarian":
        if any(_word_in_text(kw, lower) for kw in MEAT_POULTRY_KEYWORDS):
            return False

    return True


# ──────────────────────────────────────────────────────────────────────
# MEAL RECOMMENDATION
# ──────────────────────────────────────────────────────────────────────

def _determine_next_meal_type(today_meals: list[Meal]) -> str:
    """
    Determine the next meal based strictly on what the user has already logged today.
    Breakfast -> Lunch -> Dinner -> Snack.
    """
    logged_types = {
        m.meal_type.lower()
        for m in today_meals
        if getattr(m, "meal_type", None)
    }

    if "breakfast" not in logged_types:
        return "breakfast"
    if "lunch" not in logged_types:
        return "lunch"
    if "dinner" not in logged_types:
        return "dinner"
    return "snack"


def _recommend_meal(
    session: Session,
    user: User,
    goal: UserGoal | None,
    today_meals: list[Meal],
    cal_remaining: float,
    protein_remaining: float,
) -> RecommendationResponse:
    """
    Pick a coherent meal combination (e.g. Rice + Chicken + Eggs) from the database
    that fits the remaining nutritional budget and dietary preferences.
    """
    next_meal = _determine_next_meal_type(today_meals)
    goal_type = (goal.goal_type if goal else None) or "maintain_weight"
    dietary_pref = (goal.dietary_preference or "").lower().strip() if goal else ""
    avoid_list = parse_avoid_terms(goal.foods_to_avoid if goal else "")

    # Load all available active foods
    all_foods: list[FoodItem] = session.exec(
        select(FoodItem).where(
            FoodItem.deleted_at.is_(None),
            FoodItem.user_id.is_(None),
            FoodItem.kind == "catalog",
        )
    ).all()

    allowed_foods = [
        f for f in all_foods
        if _is_food_allowed(f.name, dietary_pref, avoid_list)
    ]

    if not allowed_foods:
        return RecommendationResponse(
            has_recommendation=True,
            type="meal",
            title=f"Recommended {next_meal.capitalize()}",
            meal_type=next_meal,
            reason=(
                f"You still need approximately {int(cal_remaining)} kcal and {int(protein_remaining)}g of protein today. "
                "No foods matching your dietary preferences were found in the database. Add foods to see suggestions!"
            ),
            items=[],
        )

    # Classify allowed foods into functional meal roles
    def _find_food(keywords: list[str]) -> FoodItem | None:
        for kw in keywords:
            for f in allowed_foods:
                if kw in f.name.lower():
                    return f
        return None

    # Role definitions:
    # Breakfast components
    oatmeal_food = _find_food(["oatmeal", "oat", "porridge", "cereal"])
    banana_food = _find_food(["banana", "apple", "berry", "fruit"])
    yogurt_food = _find_food(["greek yogurt", "yogurt"])
    egg_food = _find_food(["boiled egg", "egg"])

    # Lunch/Dinner components
    rice_food = _find_food(["brown rice", "rice", "quinoa", "potato", "pasta", "bread"])
    chicken_food = _find_food(["chicken breast", "chicken", "turkey", "beef"])
    salmon_food = _find_food(["salmon fillet", "salmon", "fish", "tuna"])
    tofu_food = _find_food(["tofu", "beans", "lentils"])

    selected_items: list[tuple[FoodItem, float, str]] = []  # (food, grams, description)
    meal_calorie_cap = min(cal_remaining, 750.0)

    if next_meal == "breakfast":
        # Realistic breakfast combination: Oatmeal + Fruit + Yogurt/Egg
        if oatmeal_food:
            oat_g = 60.0 if cal_remaining < 400 else 100.0
            selected_items.append((oatmeal_food, oat_g, f"{int(oat_g)}g bowl"))
        if banana_food:
            selected_items.append((banana_food, 118.0, "1 medium banana (118g)"))
        if yogurt_food:
            yog_g = 150.0 if cal_remaining > 350 else 100.0
            selected_items.append((yogurt_food, yog_g, f"{int(yog_g)}g cup"))
        elif egg_food:
            selected_items.append((egg_food, 100.0, "2 boiled eggs (100g)"))
    elif next_meal in ("lunch", "dinner"):
        # Realistic lunch/dinner combination: Carb (Rice) + Protein (Chicken/Salmon/Tofu) + Side (Egg/Yogurt)
        # Primary protein
        main_protein = None
        if dietary_pref in ("vegetarian", "vegan"):
            main_protein = tofu_food or egg_food
        elif dietary_pref == "pescatarian":
            main_protein = salmon_food or egg_food
        else:
            main_protein = chicken_food or salmon_food or egg_food

        # Carb base
        carb_base = rice_food or oatmeal_food

        if carb_base:
            rice_g = 150.0 if cal_remaining < 500 else 200.0
            selected_items.append((carb_base, rice_g, f"{int(rice_g)}g cooked"))
        if main_protein:
            prot_g = 120.0 if cal_remaining < 500 else 170.0
            selected_items.append((main_protein, prot_g, f"{int(prot_g)}g serving"))
        # Complementary side (e.g. Boiled Egg)
        if egg_food and egg_food.id != (main_protein.id if main_protein else None) and cal_remaining >= 500:
            selected_items.append((egg_food, 50.0, "1 large egg (50g)"))
        elif yogurt_food and yogurt_food.id != (main_protein.id if main_protein else None) and cal_remaining >= 450:
            selected_items.append((yogurt_food, 100.0, "100g serving"))
    else:  # snack
        # Lighter snack combination
        if yogurt_food and banana_food and cal_remaining >= 250:
            selected_items.append((yogurt_food, 150.0, "150g cup"))
            selected_items.append((banana_food, 118.0, "1 medium banana"))
        elif egg_food and cal_remaining >= 150:
            selected_items.append((egg_food, 100.0, "2 boiled eggs (100g)"))
        elif banana_food:
            selected_items.append((banana_food, 118.0, "1 medium banana (118g)"))
        elif yogurt_food:
            selected_items.append((yogurt_food, 150.0, "150g cup"))

    # Fallback if specific archetype foods were not found: pick top 1-3 allowed foods
    if not selected_items:
        # Sort allowed foods by protein density
        allowed_foods.sort(
            key=lambda f: f.protein_per_100g / max(f.calories_per_100g, 1),
            reverse=True,
        )
        accum_cal = 0.0
        for f in allowed_foods[:3]:
            if accum_cal >= meal_calorie_cap:
                break
            serving_g = min(150.0, max(50.0, (meal_calorie_cap - accum_cal) / max(f.calories_per_100g, 1) * 100))
            nutr = _nutrition_per_grams(f, serving_g)
            selected_items.append((f, serving_g, f"{int(serving_g)}g serving"))
            accum_cal += nutr["calories"]

    # Build response items
    items = []
    total_meal_cal = 0.0
    total_meal_protein = 0.0
    for food, g, desc in selected_items:
        nutr = _nutrition_per_grams(food, g)
        total_meal_cal += nutr["calories"]
        total_meal_protein += nutr["protein"]
        items.append(
            RecommendationItem(
                name=food.name,
                food_id=food.id,
                calories=nutr["calories"],
                protein=nutr["protein"],
                carbs=nutr["carbs"],
                fat=nutr["fat"],
                quantity=g,
                unit="g",
                gram_weight=g,
                description=desc,
            )
        )

    combo_names = " + ".join(f.name for f, _, _ in selected_items)
    reason = (
        f"Based on your '{goal_type.replace('_', ' ')}' goal and remaining budget "
        f"({int(cal_remaining)} kcal, {int(protein_remaining)}g protein). "
        f"Enjoy {combo_names} for a balanced {next_meal}."
    )

    return RecommendationResponse(
        has_recommendation=True,
        type="meal",
        title=f"Recommended {next_meal.capitalize()}",
        meal_type=next_meal,
        reason=reason,
        items=items,
    )


# ──────────────────────────────────────────────────────────────────────
# EXERCISE RECOMMENDATION & EQUIPMENT COMPATIBILITY
# ──────────────────────────────────────────────────────────────────────

EQUIPMENT_CANONICAL: dict[str, str] = {
    "barbell": "barbell",
    "barbells": "barbell",
    "dumbbell": "dumbbell",
    "dumbbells": "dumbbell",
    "machine": "machines",
    "machines": "machines",
    "cable": "cables",
    "cables": "cables",
    "band": "bands",
    "bands": "bands",
    "resistance band": "bands",
    "resistance bands": "bands",
    "kettlebell": "kettlebell",
    "kettlebells": "kettlebell",
    "bodyweight": "bodyweight",
    "body weight": "bodyweight",
    "bodyweight only": "bodyweight",
    "none": "bodyweight",
    "no equipment": "bodyweight",
}


def normalize_equipment_set(equipment_str: str | None) -> set[str]:
    """Parse and canonicalize user's comma-separated equipment string."""
    if not equipment_str or not equipment_str.strip():
        return set()
    raw_tokens = [e.strip().lower() for e in equipment_str.split(",") if e.strip()]
    normalized: set[str] = set()
    for token in raw_tokens:
        canon = EQUIPMENT_CANONICAL.get(token, token)
        normalized.add(canon)
    return normalized


def is_equipment_compatible(item_equipment: str | None, user_equipment: set[str]) -> bool:
    """
    Check if an exercise's required equipment is compatible with what the user has.

    Rules:
    - If user specified no equipment restrictions (empty user_equipment), all exercises are allowed.
    - If user specified "none" or "bodyweight", ONLY bodyweight exercises are allowed.
    - "bodyweight" exercises require no equipment and are ALWAYS compatible for any user.
    - Multi-option catalog equipment (joined by "|", e.g. "barbell|dumbbell") is compatible
      if the user has at least one of those pieces of equipment.
    """
    if not user_equipment:
        return True

    user_have = {EQUIPMENT_CANONICAL.get(e, e) for e in user_equipment}
    allowed_gear = user_have - {"bodyweight"}

    item_str = (item_equipment or "bodyweight").lower().strip()
    item_options = {
        EQUIPMENT_CANONICAL.get(part.strip(), part.strip())
        for part in item_str.split("|")
        if part.strip()
    }

    # Bodyweight exercises are universally doable
    if "bodyweight" in item_options:
        return True

    # If the user only has bodyweight/none, non-bodyweight exercises are excluded
    if not allowed_gear:
        return False

    return bool(item_options & allowed_gear)


def _equipment_ok(item_equipment: str | None, user_equipment: set[str]) -> bool:
    """Backwards-compatible wrapper around is_equipment_compatible."""
    return is_equipment_compatible(item_equipment, user_equipment)


# ──────────────────────────────────────────────────────────────────────
# MAIN ENGINE
# ──────────────────────────────────────────────────────────────────────

def get_recommendation(
    session: Session,
    user: User,
    today: Date | None = None,
    rec_type: str | None = None,
) -> RecommendationResponse:
    """
    Main recommendation endpoint logic.

    Answers: "What is useful for me to do next today?"
    Combines:
    - User goal & profile (weight, activity level)
    - Today's meals & meal types
    - Today's calories and protein consumed vs target
    - Today's exercises & training adequacy evaluation
    - Muscle-group coverage and weekly volume
    - Available equipment & dietary restrictions
    """
    if today is None:
        today = Date.today()

    # ── Fetch user goal ──────────────────────────────────────────
    goal: UserGoal | None = session.exec(
        select(UserGoal).where(UserGoal.user_id == user.id)
    ).first()

    # ── Fetch today's meals ─────────────────────────────────────
    today_meals: list[Meal] = session.exec(
        select(Meal).where(
            Meal.user_id == user.id,
            Meal.date == today,
            Meal.deleted_at.is_(None),
        )
    ).all()

    total_cal = sum(m.calories for m in today_meals)
    total_protein = sum(m.protein for m in today_meals)

    # ── Fetch today's current session exercises ─────────────────
    from src.services.training_service import (
        evaluate_training_adequacy,
        get_current_session_exercises,
    )

    today_exercises: list[Exercise] = get_current_session_exercises(
        session=session,
        user_id=user.id,
        today=today,
    )

    # ── Target calculation ──────────────────────────────────────
    cal_target, protein_target = _calculate_targets(user, goal)
    cal_remaining = max(0.0, cal_target - total_cal)
    protein_remaining = max(0.0, protein_target - total_protein)

    # ── Training adequacy evaluation ─────────────────────────────
    adequacy = evaluate_training_adequacy(
        session=session,
        user_id=user.id,
        goal=goal,
        today=today,
    )

    # Derive exercise completion vs rest-day state from training adequacy
    workout_completed = adequacy.session_action == "workout_adequate"
    is_rest_day = adequacy.session_action == "rest"
    exercise_done = workout_completed or is_rest_day

    # Nutrition completion: within 90% calories and 85% protein, or < 150 kcal remaining
    cal_done = total_cal >= cal_target * 0.90 or cal_remaining < 150
    protein_done = total_protein >= protein_target * 0.85
    nutrition_done = cal_done and protein_done

    # ── Explicit type request handling ─────────────────────────
    if rec_type == "exercise":
        if exercise_done:
            if is_rest_day:
                reason = (
                    "Today is a scheduled rest day based on your weekly training target. "
                    "Rest up and recover!"
                )
            else:
                ex_names = ", ".join(e.name for e in today_exercises) if today_exercises else ""
                reason = (
                    f"You have completed enough work for this session ({ex_names}). "
                    f"{adequacy.detail} "
                    "Great work – make sure to rest and recover!"
                )
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason=reason,
                items=[],
            )
        return _recommend_exercise_with_adequacy(
            session, user, goal, today_exercises, adequacy, today=today
        )

    if rec_type == "meal":
        if nutrition_done or cal_remaining < MIN_CALORIE_REMAINING:
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason=(
                    f"You've consumed {int(total_cal)} of your {int(cal_target)} kcal target for today. "
                    "Your nutrition goals are well on track!"
                ),
                items=[],
            )
        return _recommend_meal(
            session, user, goal, today_meals, cal_remaining, protein_remaining
        )

    # ── General recommendation (rec_type is None) ───────────────
    sessions_today = len(today_exercises)

    # Case 1: Both nutrition and exercise/rest are satisfied
    if nutrition_done and exercise_done:
        if is_rest_day:
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason=(
                    "Today is a scheduled rest day and you've hit your nutrition targets. "
                    "Rest up and recover!"
                ),
            )
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason=(
                "You've hit your nutrition targets and completed your workout for today. "
                "Great job – you're all set!"
            ),
        )

    # Case 2: In-progress incomplete workout
    # If the user has started a workout today and it is not adequate yet,
    # prioritize the workout over meal suggestions (do not prematurely suppress with dinner).
    if sessions_today > 0 and not exercise_done:
        return _recommend_exercise_with_adequacy(
            session, user, goal, today_exercises, adequacy, today=today
        )

    # Case 3: Nothing logged yet today
    # Recommend starting the day with Breakfast!
    logged_types = {
        m.meal_type.lower()
        for m in today_meals
        if getattr(m, "meal_type", None)
    }

    if not today_meals and sessions_today == 0:
        return _recommend_meal(
            session, user, goal, today_meals, cal_remaining, protein_remaining
        )

    # Case 4: Breakfast or lunch logged, but workout not completed yet
    # Natural flow: fuel up -> do workout!
    if not exercise_done and ("breakfast" in logged_types or "lunch" in logged_types):
        return _recommend_exercise_with_adequacy(
            session, user, goal, today_exercises, adequacy, today=today
        )

    # Case 5: Exercise done, next meal needed
    if exercise_done and not nutrition_done and cal_remaining >= MIN_CALORIE_REMAINING:
        return _recommend_meal(
            session, user, goal, today_meals, cal_remaining, protein_remaining
        )

    # Case 6: Nutrition not done, calories remain
    if not nutrition_done and cal_remaining >= MIN_CALORIE_REMAINING:
        return _recommend_meal(
            session, user, goal, today_meals, cal_remaining, protein_remaining
        )

    # Case 7: Nutrition is done, but exercise remains
    if not exercise_done:
        return _recommend_exercise_with_adequacy(
            session, user, goal, today_exercises, adequacy, today=today
        )

    # Default fallback: on track
    return RecommendationResponse(
        has_recommendation=False,
        type="none",
        reason="You're on track for today – both your nutrition and workout look good!",
    )


# ──────────────────────────────────────────────────────────────────────
# PRESCRIPTION BOUNDS & PROGRESSION HELPERS
# ──────────────────────────────────────────────────────────────────────

STRENGTH_SETS_BOUNDS: tuple[int, int] = (2, 5)
STRENGTH_COMPOUND_REP_BOUNDS: tuple[int, int] = (4, 12)
STRENGTH_ISOLATION_REP_BOUNDS: tuple[int, int] = (8, 15)
STRENGTH_REST_BOUNDS_SECONDS: tuple[int, int] = (60, 180)

BODYWEIGHT_SETS_BOUNDS: tuple[int, int] = (2, 4)
BODYWEIGHT_HARD_REP_BOUNDS: tuple[int, int] = (4, 12)
BODYWEIGHT_STANDARD_REP_BOUNDS: tuple[int, int] = (8, 20)
BODYWEIGHT_HOLD_DURATION_BOUNDS: tuple[int, int] = (1, 3)

CARDIO_HIIT_DURATION_BOUNDS: tuple[int, int] = (10, 25)
CARDIO_STEADY_DURATION_BOUNDS: tuple[int, int] = (15, 45)
FLEXIBILITY_DURATION_BOUNDS: tuple[int, int] = (10, 30)

# Maximum days since last comparable session before progression is held back as stale
MAX_COMPARABLE_HISTORY_DAYS = 21

ISOMETRIC_HOLD_NAMES: set[str] = {"plank", "side plank", "dead hang"}
HIGH_DIFFICULTY_BODYWEIGHT_NAMES: set[str] = {
    "pull-ups",
    "chin-ups",
    "dips",
    "pike push-ups",
    "hanging leg raise",
    "planche push-up",
}
HIGH_INTENSITY_CARDIO_NAMES: set[str] = {
    "hiit",
    "burpees",
    "jump rope",
    "mountain climbers",
    "jumping jacks",
    "boxing",
    "stair climber",
}


def _clamp_int(val: int, bounds: tuple[int, int]) -> int:
    return max(bounds[0], min(bounds[1], int(val)))


def _format_days_ago(today: Date, log_date: Date) -> str:
    days_ago = (today - log_date).days
    if days_ago <= 0:
        return "today"
    if days_ago == 1:
        return "1 day ago"
    return f"{days_ago} days ago"


def _is_isometric_hold(item: ExerciseCatalogItem) -> bool:
    name_lower = (item.name or "").strip().lower()
    return (
        name_lower in ISOMETRIC_HOLD_NAMES
        or "plank" in name_lower
        or "dead hang" in name_lower
    )


def _is_high_difficulty_bodyweight(item: ExerciseCatalogItem) -> bool:
    name_lower = (item.name or "").strip().lower()
    return name_lower in HIGH_DIFFICULTY_BODYWEIGHT_NAMES


def _is_bodyweight_prescription(
    item: ExerciseCatalogItem,
    user_equipment: set[str],
) -> bool:
    item_str = (item.equipment or "bodyweight").lower().strip()
    item_options = {
        EQUIPMENT_CANONICAL.get(part.strip(), part.strip())
        for part in item_str.split("|")
        if part.strip()
    }
    non_bw_options = item_options - {"bodyweight"}
    if not non_bw_options:
        return True
    if not user_equipment:
        return False
    user_have = {EQUIPMENT_CANONICAL.get(e, e) for e in user_equipment} - {"bodyweight"}
    return not bool(non_bw_options & user_have)


def _is_isolation_exercise(item: ExerciseCatalogItem, mappings: list) -> bool:
    primaries = [m for m in mappings if m.role == "primary"]
    if any((m.movement_pattern or "").lower() == "isolation" for m in primaries):
        return True
    primary_groups = {m.muscle_group for m in primaries}
    if primary_groups and primary_groups.issubset({"biceps", "triceps", "forearms", "calves"}):
        return True
    return False


def _is_high_intensity_cardio(item: ExerciseCatalogItem) -> bool:
    name_lower = (item.name or "").strip().lower()
    return name_lower in HIGH_INTENSITY_CARDIO_NAMES


def _get_valid_exercise_history(
    session: Session,
    user_id: int,
    item: ExerciseCatalogItem,
    today: Date,
) -> list[Exercise]:
    """
    Fetch valid historical logs for `item` up to `today`, excluding soft-deleted
    rows, logs linked to a different catalog item, and logs in abandoned sessions.
    """
    name_lower = (item.name or "").strip().lower()
    if item.id is not None:
        match_cond = or_(
            Exercise.exercise_catalog_id == item.id,
            and_(
                Exercise.exercise_catalog_id.is_(None),
                func.lower(Exercise.name) == name_lower,
            ),
        )
    else:
        match_cond = func.lower(Exercise.name) == name_lower

    abandoned_ids = set(
        session.exec(
            select(WorkoutSession.id).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.status == "abandoned",
            )
        ).all()
    )

    rows = session.exec(
        select(Exercise)
        .where(
            Exercise.user_id == user_id,
            Exercise.deleted_at.is_(None),
            Exercise.date <= today,
            match_cond,
        )
        .order_by(Exercise.date.desc(), Exercise.id.desc())
    ).all()

    return [
        r for r in rows
        if r.workout_session_id is None or r.workout_session_id not in abandoned_ids
    ]


def _is_comparable_weighted_log(ex: Exercise, target_reps: int) -> bool:
    """
    A weighted strength log is comparable to `target_reps` only when:
    - weight_kg > 0 and reps > 0
    - sets is None or within [1, 10]
    - reps is within a comparable working band around `target_reps`
      (excludes 1-2 rep max tests and ultra-high-rep warmups/burnouts).
    """
    if ex.weight_kg is None or ex.weight_kg <= 0:
        return False
    if ex.reps is None or ex.reps <= 0:
        return False
    if ex.sets is not None and (ex.sets <= 0 or ex.sets > 10):
        return False

    min_comp_reps = max(3 if target_reps >= 5 else 2, target_reps - 4)
    max_comp_reps = target_reps + 6
    return min_comp_reps <= ex.reps <= max_comp_reps


def _conservative_load_step(weight_kg: float, is_isolation: bool) -> float:
    """
    Determine a conservative load increment/decrement step (rounded to 0.5 kg)
    that never exceeds 10% of the working weight or 2.5 kg.
    """
    base_step = 1.0 if (weight_kg < 15.0 or (is_isolation and weight_kg < 20.0)) else 2.5
    max_pct_step = max(0.5, round((weight_kg * 0.10) * 2.0) / 2.0)
    return min(base_step, max_pct_step)


def _prescribe_weighted_strength(
    item: ExerciseCatalogItem,
    mappings: list,
    goal_type: str,
    experience: str,
    history_logs: list[Exercise],
    today: Date,
) -> tuple[int, int, int, float | None, str | None, str | None]:
    """
    Return (sets, reps, rest_seconds, suggested_weight_kg, last_performance, progression_note)
    for a weighted strength exercise using comparable past performance and trends.
    """
    from src.services.training_service import EFFORT_RATING_LABELS

    is_iso = _is_isolation_exercise(item, mappings)

    if is_iso:
        if experience == "beginner":
            base_sets, base_reps, rest_sec = 3, 10, 60
        elif experience == "intermediate":
            base_sets, base_reps, rest_sec = 3, (10 if goal_type == "get_stronger" else 12), 75
        else:
            base_sets, base_reps, rest_sec = 4, (10 if goal_type == "get_stronger" else 12), 90
        sets = _clamp_int(base_sets, (2, 4))
        reps = _clamp_int(base_reps, STRENGTH_ISOLATION_REP_BOUNDS)
    else:
        if experience == "beginner":
            base_sets = 3
            base_reps = 8 if goal_type == "get_stronger" else 10
            rest_sec = 120 if goal_type == "get_stronger" else 90
        elif experience == "intermediate":
            base_sets = 4
            base_reps = 6 if goal_type == "get_stronger" else 8
            rest_sec = 150 if goal_type == "get_stronger" else 120
        else:
            base_sets = 5 if goal_type in ("get_stronger", "build_muscle", "gain_weight") else 4
            base_reps = 5 if goal_type in ("get_stronger", "build_muscle", "gain_weight") else 6
            rest_sec = 180 if goal_type == "get_stronger" else 150
        sets = _clamp_int(base_sets, STRENGTH_SETS_BOUNDS)
        reps = _clamp_int(base_reps, STRENGTH_COMPOUND_REP_BOUNDS)

    rest_sec = _clamp_int(rest_sec, STRENGTH_REST_BOUNDS_SECONDS)

    weighted_logs = [
        e for e in history_logs
        if e.weight_kg is not None and e.weight_kg > 0
    ]
    if not weighted_logs:
        return sets, reps, rest_sec, None, None, None

    comparable_logs = [
        e for e in weighted_logs
        if _is_comparable_weighted_log(e, reps)
    ]

    if not comparable_logs:
        non_comp = weighted_logs[0]
        when_str = _format_days_ago(today, non_comp.date)
        effort_label = (
            EFFORT_RATING_LABELS.get(non_comp.effort_rating)
            if non_comp.effort_rating is not None
            else None
        )
        effort_str = f" ({effort_label})" if effort_label else ""
        last_perf = (
            f"Last time: {non_comp.weight_kg:g} kg x "
            f"{non_comp.reps or 0}{effort_str}, {when_str}"
        )
        prog_note = (
            f"Prior log ({non_comp.weight_kg:g} kg × {non_comp.reps or 0}) used a non-comparable "
            f"rep scheme for a {reps}-rep target, so no automatic load progression is applied"
        )
        return sets, reps, rest_sec, None, last_perf, prog_note

    latest = comparable_logs[0]
    prev = comparable_logs[1] if len(comparable_logs) >= 2 else None
    days_ago = (today - latest.date).days
    when_str = _format_days_ago(today, latest.date)
    effort_label = (
        EFFORT_RATING_LABELS.get(latest.effort_rating)
        if latest.effort_rating is not None
        else None
    )
    effort_str = f" ({effort_label})" if effort_label else ""
    last_perf = (
        f"Last time: {latest.weight_kg:g} kg x "
        f"{latest.reps or 0}{effort_str}, {when_str}"
    )

    step_kg = _conservative_load_step(latest.weight_kg, is_iso)
    min_required_sets = max(2, sets - 1)
    sets_completed_ok = latest.sets is None or latest.sets >= min_required_sets

    # 1. Stale comparable history (> 21 days ago): hold weight conservatively
    if days_ago > MAX_COMPARABLE_HISTORY_DAYS:
        suggested_weight = round(latest.weight_kg * 2.0) / 2.0
        prog_note = (
            f"Maintaining {suggested_weight:g} kg because your last comparable session "
            f"was {days_ago} days ago"
        )
        return sets, reps, rest_sec, suggested_weight, last_perf, prog_note

    # 2. Multi-session downward trend / consecutive missed targets at same or higher weight -> conservative deload
    if (
        prev is not None
        and (latest.date - prev.date).days <= 28
        and latest.reps is not None
        and prev.reps is not None
        and latest.reps < reps
        and prev.reps < reps
        and prev.weight_kg is not None
        and prev.weight_kg >= latest.weight_kg
        and (
            latest.effort_rating in (4, 5)
            or prev.effort_rating in (4, 5)
            or latest.reps < prev.reps
        )
    ):
        raw_w = max(2.5, latest.weight_kg - step_kg)
        suggested_weight = round(raw_w * 2.0) / 2.0
        prog_note = (
            f"Recent trend shows missed target reps across consecutive sessions; "
            f"conservatively reducing load to {suggested_weight:g} kg (-{step_kg:g} kg) to rebuild volume"
        )
        return sets, reps, rest_sec, suggested_weight, last_perf, prog_note

    # 3. Latest session missed target reps -> hold weight
    if latest.reps is None or latest.reps < reps:
        suggested_weight = round(latest.weight_kg * 2.0) / 2.0
        prog_note = (
            f"Maintaining {suggested_weight:g} kg until all {reps} target reps are achieved"
        )
        return sets, reps, rest_sec, suggested_weight, last_perf, prog_note

    # 4. Latest session had insufficient working sets -> hold weight to complete set volume
    if not sets_completed_ok:
        suggested_weight = round(latest.weight_kg * 2.0) / 2.0
        prog_note = (
            f"Maintaining {suggested_weight:g} kg to build up to {sets} working sets "
            f"(completed {latest.sets} set(s) last time)"
        )
        return sets, reps, rest_sec, suggested_weight, last_perf, prog_note

    # 5. Unknown effort rating -> never treat unknown effort as a known manageable rating
    if latest.effort_rating is None:
        suggested_weight = round(latest.weight_kg * 2.0) / 2.0
        prog_note = (
            f"Maintaining {suggested_weight:g} kg because effort rating was not recorded "
            "on your last comparable session"
        )
        return sets, reps, rest_sec, suggested_weight, last_perf, prog_note

    # 6. Extremely Hard effort (5) -> hold weight to consolidate form
    if latest.effort_rating >= 5:
        suggested_weight = round(latest.weight_kg * 2.0) / 2.0
        prog_note = (
            f"Maintaining {suggested_weight:g} kg to consolidate form after an Extremely Hard session"
        )
        return sets, reps, rest_sec, suggested_weight, last_perf, prog_note

    # 7. Trend consolidation: if user just increased load or recovered from a prior miss/max-effort session
    # and the latest session was still Hard (4), hold weight for one more session before adding more load.
    if (
        prev is not None
        and (latest.date - prev.date).days <= MAX_COMPARABLE_HISTORY_DAYS
        and latest.effort_rating == 4
        and prev.weight_kg is not None
    ):
        if latest.weight_kg > prev.weight_kg:
            suggested_weight = round(latest.weight_kg * 2.0) / 2.0
            prog_note = (
                f"Consolidating recent load increase at {suggested_weight:g} kg (rated Hard) "
                "before progressing further"
            )
            return sets, reps, rest_sec, suggested_weight, last_perf, prog_note
        if (prev.reps is not None and prev.reps < reps) or prev.effort_rating == 5:
            suggested_weight = round(latest.weight_kg * 2.0) / 2.0
            prog_note = (
                f"Consolidating {suggested_weight:g} kg after recovering from a tough prior session"
            )
            return sets, reps, rest_sec, suggested_weight, last_perf, prog_note

    # 8. Manageable effort (1-4) with target reps & sets completed -> conservative load increase
    raw_w = latest.weight_kg + step_kg
    suggested_weight = round(raw_w * 2.0) / 2.0
    prog_note = (
        f"Conservatively progressing to {suggested_weight:g} kg (+{step_kg:g} kg) "
        f"based on completing {latest.reps} reps with {effort_label} effort"
    )
    return sets, reps, rest_sec, suggested_weight, last_perf, prog_note


def _prescribe_bodyweight_strength(
    item: ExerciseCatalogItem,
    experience: str,
    history_logs: list[Exercise],
    today: Date,
) -> tuple[int, int, int | None, int, str | None, str | None]:
    """
    Return (sets, reps, duration_minutes, rest_seconds, last_performance, progression_note)
    for a bodyweight strength exercise, enforcing sensible bounds on sets, reps, duration, and rest.
    """
    from src.services.training_service import EFFORT_RATING_LABELS

    if _is_isometric_hold(item):
        base_sets = 3 if experience in ("beginner", "intermediate") else 4
        base_dur = 1 if experience == "beginner" else (2 if experience == "intermediate" else 3)
        sets = _clamp_int(base_sets, BODYWEIGHT_SETS_BOUNDS)
        duration = _clamp_int(base_dur, BODYWEIGHT_HOLD_DURATION_BOUNDS)
        return sets, 1, duration, 60, None, None

    is_hard_bw = _is_high_difficulty_bodyweight(item)
    rep_bounds = BODYWEIGHT_HARD_REP_BOUNDS if is_hard_bw else BODYWEIGHT_STANDARD_REP_BOUNDS

    if is_hard_bw:
        base_sets = 3 if experience in ("beginner", "intermediate") else 4
        base_reps = 6 if experience == "beginner" else (8 if experience == "intermediate" else 10)
        rest_sec = 90 if experience in ("beginner", "intermediate") else 120
    else:
        base_sets = 3 if experience in ("beginner", "intermediate") else 4
        base_reps = 10 if experience == "beginner" else (12 if experience == "intermediate" else 15)
        rest_sec = 60 if experience in ("beginner", "intermediate") else 75

    sets = _clamp_int(base_sets, BODYWEIGHT_SETS_BOUNDS)
    reps = _clamp_int(base_reps, rep_bounds)
    rest_sec = _clamp_int(rest_sec, STRENGTH_REST_BOUNDS_SECONDS)

    bw_logs = [
        e for e in history_logs
        if (e.weight_kg is None or e.weight_kg == 0)
        and e.reps is not None
        and e.reps > 0
        and (e.sets is None or e.sets > 0)
    ]
    if not bw_logs:
        return sets, reps, None, rest_sec, None, None

    latest = bw_logs[0]
    days_ago = (today - latest.date).days
    when_str = _format_days_ago(today, latest.date)
    effort_label = (
        EFFORT_RATING_LABELS.get(latest.effort_rating)
        if latest.effort_rating is not None
        else None
    )
    effort_str = f" ({effort_label})" if effort_label else ""
    last_perf = f"Last time: {latest.sets or sets} sets x {latest.reps} reps{effort_str}, {when_str}"

    # Clamp historical reference reps/sets to sensible bodyweight bounds
    ref_reps = _clamp_int(latest.reps, rep_bounds)
    ref_sets = _clamp_int(latest.sets or sets, BODYWEIGHT_SETS_BOUNDS)

    if days_ago > MAX_COMPARABLE_HISTORY_DAYS:
        return sets, ref_reps, None, rest_sec, last_perf, (
            f"Maintaining {sets}×{ref_reps} within bodyweight bounds after {days_ago} days away"
        )

    if latest.effort_rating is None:
        return sets, max(reps, ref_reps), None, rest_sec, last_perf, (
            "Maintaining bodyweight prescription because effort rating was unknown last time"
        )

    if latest.effort_rating >= 5 or latest.reps < base_reps:
        return sets, ref_reps, None, rest_sec, last_perf, (
            f"Maintaining {sets}×{ref_reps} reps to consolidate bodyweight form"
        )

    # Known manageable effort (1-4): progress reps conservatively within rep_bounds, then sets up to 4
    rep_step = 2 if latest.effort_rating <= 3 else 1
    if ref_reps < rep_bounds[1]:
        new_reps = _clamp_int(max(reps, ref_reps) + rep_step, rep_bounds)
        prog_note = (
            f"Progressing bodyweight volume to {sets}×{new_reps} reps "
            f"after {effort_label} effort"
        )
        return sets, new_reps, None, rest_sec, last_perf, prog_note

    new_sets = _clamp_int(max(sets, ref_sets) + 1, BODYWEIGHT_SETS_BOUNDS)
    prog_note = (
        f"At the {rep_bounds[1]}-rep bodyweight ceiling; prescribing {new_sets}×{rep_bounds[1]} reps"
    )
    return new_sets, rep_bounds[1], None, rest_sec, last_perf, prog_note


def _prescribe_cardio(
    item: ExerciseCatalogItem,
    goal_type: str,
    experience: str,
    history_logs: list[Exercise],
    today: Date,
) -> tuple[int, int | None, str | None, str | None]:
    """
    Return (duration_minutes, rest_seconds, last_performance, progression_note)
    for a cardio exercise, enforcing sensible bounds for steady-state vs HIIT cardio.
    """
    from src.services.training_service import EFFORT_RATING_LABELS

    is_hiit = _is_high_intensity_cardio(item)
    bounds = CARDIO_HIIT_DURATION_BOUNDS if is_hiit else CARDIO_STEADY_DURATION_BOUNDS
    rest_sec = 60 if is_hiit else None

    if is_hiit:
        if experience == "beginner":
            base_dur = 15
        elif experience == "intermediate":
            base_dur = 20
        else:
            base_dur = 25
    else:
        if experience == "beginner":
            base_dur = 25 if goal_type == "improve_endurance" else 20
        elif experience == "intermediate":
            base_dur = 35 if goal_type == "improve_endurance" else 30
        else:
            base_dur = 45 if goal_type == "improve_endurance" else 40

    duration = _clamp_int(base_dur, bounds)

    cardio_logs = [
        e for e in history_logs
        if e.duration_minutes is not None and e.duration_minutes > 0
    ]
    if not cardio_logs:
        return duration, rest_sec, None, None

    latest = cardio_logs[0]
    days_ago = (today - latest.date).days
    when_str = _format_days_ago(today, latest.date)
    effort_label = (
        EFFORT_RATING_LABELS.get(latest.effort_rating)
        if latest.effort_rating is not None
        else None
    )
    effort_str = f" ({effort_label})" if effort_label else ""
    last_perf = f"Last time: {latest.duration_minutes} min{effort_str}, {when_str}"

    # Clamp historical duration to sensible bounds so extreme past logs (e.g. 3 min or 180 min)
    # never produce an unbounded cardio prescription
    ref_dur = _clamp_int(latest.duration_minutes, bounds)

    if days_ago > MAX_COMPARABLE_HISTORY_DAYS or latest.effort_rating is None or latest.effort_rating >= 5:
        target_dur = _clamp_int(max(duration, ref_dur) if latest.effort_rating in (1, 2, 3, 4) else ref_dur, bounds)
        # Ensure we never drop below base_dur unless latest was a recent valid effort=5 session within bounds
        if latest.duration_minutes < bounds[0] or latest.effort_rating is None:
            target_dur = duration
        return target_dur, rest_sec, last_perf, None

    # Manageable effort (1-4) and met or exceeded base duration -> conservative +5 min within bounds
    if latest.duration_minutes >= duration and ref_dur < bounds[1]:
        new_dur = _clamp_int(ref_dur + 5, bounds)
        prog_note = (
            f"Conservatively progressing cardio duration to {new_dur} minutes "
            f"after {effort_label} effort"
        )
        return new_dur, rest_sec, last_perf, prog_note

    return _clamp_int(max(duration, ref_dur), bounds), rest_sec, last_perf, None


def _recommend_exercise_with_adequacy(
    session: Session,
    user: User,
    goal: UserGoal | None,
    today_exercises: list[Exercise],
    adequacy,
    today: Date | None = None,
) -> RecommendationResponse:
    """
    Workout-aware exercise recommendation.

    Uses training adequacy data to recommend exercises that target
    undertrained muscle groups, respecting the current session's
    split context, available equipment, experience level, and recent
    training history. Avoids recommending exercises already completed
    that day when suitable alternatives exist.

    Handles distinct scenarios:
    1. Incompatible equipment or no exercises in catalog -> explain clearly
    2. All compatible exercises already completed today -> explain clearly
    3. Session adequate -> no more recommendations needed (recover)
    4. Session not adequate -> recommend best matching exercise with reasoning
    """
    if today is None:
        today = Date.today()

    goal_type = (goal.goal_type if goal else None) or "improve_fitness"
    experience = (goal.training_experience or "beginner").lower() if goal else "beginner"
    user_equipment = normalize_equipment_set(goal.available_equipment if goal else None)

    # Load visible catalog for this user
    catalog: list[ExerciseCatalogItem] = session.exec(
        select(ExerciseCatalogItem).where(*visible_exercise(user.id))
    ).all()

    if not catalog:
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="No exercises found in the catalog. Add exercises to get recommendations.",
            items=[],
        )

    # 1. Filter catalog strictly by user equipment compatibility
    compatible_catalog = [
        item for item in catalog
        if is_equipment_compatible(item.equipment, user_equipment)
    ]

    if not compatible_catalog:
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="No exercises in the catalog match your available equipment.",
            items=[],
        )

    # 2. Collect ALL exercises completed today by this user across any session or unlinked
    # (excluding abandoned sessions) to avoid recommending exercises already completed that day
    today_all = session.exec(
        select(Exercise).where(
            Exercise.user_id == user.id,
            Exercise.date == today,
            Exercise.deleted_at.is_(None),
        )
    ).all()
    abandoned_today_ids = set(
        session.exec(
            select(WorkoutSession.id).where(
                WorkoutSession.user_id == user.id,
                WorkoutSession.date == today,
                WorkoutSession.status == "abandoned",
            )
        ).all()
    )
    completed_today = [
        e for e in today_all
        if e.workout_session_id is None or e.workout_session_id not in abandoned_today_ids
    ]
    done_today_names = {e.name.lower().strip() for e in completed_today if e.name}
    done_today_cat_ids = {e.exercise_catalog_id for e in completed_today if e.exercise_catalog_id is not None}

    # Avoid recommending exercises already completed that day when suitable alternatives exist
    uncompleted_candidates = [
        item for item in compatible_catalog
        if item.name.lower().strip() not in done_today_names
        and (item.id is None or item.id not in done_today_cat_ids)
    ]

    if uncompleted_candidates:
        eligible = uncompleted_candidates
    else:
        # All compatible exercises were already completed today!
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason=(
                "No additional compatible exercises available in the catalog. "
                "You may have covered all available options for today."
            ),
            items=[],
        )

    # Use training adequacy to find muscles that need work
    from src.services.training_service import (
        get_muscle_mappings,
        _get_relevant_muscles_for_split,
        CARDIO_PRIMARY_GOALS,
        CARDIO_SECONDARY_GOALS,
        STRENGTH_PRIMARY_GOALS,
        MAJOR_MUSCLE_GROUPS,
        UPPER_MUSCLE_GROUPS,
        LOWER_MUSCLE_GROUPS,
    )

    mappings_by_catalog_id = get_muscle_mappings(session)
    target_muscles = _get_relevant_muscles_for_split(adequacy.detected_split)

    # Find the most undertrained muscles relevant to the current split, prioritizing major muscle groups
    undertrained_muscles = sorted(
        [
            mv for mv in adequacy.muscle_volumes.values()
            if mv.status == "undertrained" and mv.muscle_group in target_muscles
        ],
        key=lambda mv: (
            0 if mv.muscle_group in MAJOR_MUSCLE_GROUPS else 1,
            mv.effective_sets / max(mv.target_min, 0.1),
        ),
    )

    needed_muscle_set = {mv.muscle_group for mv in undertrained_muscles[:4]}

    # Recent training history (yesterday and 2 days ago)
    recent_exercises = session.exec(
        select(Exercise).where(
            Exercise.user_id == user.id,
            Exercise.deleted_at.is_(None),
            Exercise.date >= today - timedelta(days=2),
            Exercise.date <= today - timedelta(days=1),
        )
    ).all()
    yesterday_exercises = [e for e in recent_exercises if e.date == today - timedelta(days=1)]
    two_days_ago_exercises = [e for e in recent_exercises if e.date == today - timedelta(days=2)]

    yesterday_ids = {e.exercise_catalog_id for e in yesterday_exercises if e.exercise_catalog_id is not None}
    yesterday_names = {e.name.lower().strip() for e in yesterday_exercises if e.name}
    two_days_ago_ids = {e.exercise_catalog_id for e in two_days_ago_exercises if e.exercise_catalog_id is not None}
    two_days_ago_names = {e.name.lower().strip() for e in two_days_ago_exercises if e.name}

    yesterday_worked_muscles: set[str] = set()
    for e in yesterday_exercises:
        if e.exercise_catalog_id:
            for m in mappings_by_catalog_id.get(e.exercise_catalog_id, []):
                if m.role == "primary":
                    yesterday_worked_muscles.add(m.muscle_group)

    # Score eligible exercises: prefer those that hit needed muscles and match context
    def _adequacy_score(item: ExerciseCatalogItem) -> float:
        """
        Lower score = better recommendation.
        Takes into account:
        - Muscle-group needs (prioritizing undertrained major muscle groups)
        - Session context (split alignment: upper vs lower)
        - Goal category (strength vs cardio)
        - Experience level (beginner vs intermediate vs advanced)
        - Recent training history (penalizing exercises/muscles worked yesterday / 2 days ago)
        """
        mappings = mappings_by_catalog_id.get(item.id, [])
        primary_muscles = {m.muscle_group for m in mappings if m.role == "primary"}
        secondary_muscles = {m.muscle_group for m in mappings if m.role == "secondary"}
        has_mappings = len(mappings) > 0

        # Primary match with needed undertrained muscles
        primary_overlap = primary_muscles & needed_muscle_set
        secondary_overlap = secondary_muscles & needed_muscle_set
        major_primary = primary_muscles & MAJOR_MUSCLE_GROUPS
        major_bonus = len(major_primary) * 15

        muscle_score = 100 - (len(primary_overlap) * 35 + len(secondary_overlap) * 12 + major_bonus)

        # ── SESSION CONTEXT: SPLIT ALIGNMENT ──
        # If the user is in an Upper or Lower session, heavily penalize exercises targeting the opposite region
        split_penalty = 0
        if adequacy.detected_split == "upper":
            if item.category == "strength" and primary_muscles and primary_muscles.issubset(LOWER_MUSCLE_GROUPS):
                split_penalty = 70
        elif adequacy.detected_split == "lower":
            if item.category == "strength" and primary_muscles and primary_muscles.issubset(UPPER_MUSCLE_GROUPS):
                split_penalty = 70

        # ── GOAL CATEGORY ALIGNMENT ──
        preferred_categories = GOAL_EXERCISE_CATEGORY.get(goal_type, ["cardio", "strength"])
        cat_bonus = 0 if item.category in preferred_categories else 40

        if goal_type in CARDIO_PRIMARY_GOALS and item.category == "cardio":
            cat_bonus = -45
        elif goal_type in STRENGTH_PRIMARY_GOALS and item.category == "strength":
            cat_bonus = -25

        if (
            goal_type in (CARDIO_PRIMARY_GOALS | CARDIO_SECONDARY_GOALS)
            and getattr(adequacy, "cardio_week", None) is not None
            and adequacy.cardio_week.status != "met"
            and item.category == "cardio"
        ):
            cat_bonus -= 15

        # Penalise unmapped strength exercises slightly
        if not has_mappings and item.category == "strength":
            muscle_score += 20

        # ── EXPERIENCE LEVEL ──
        item_level = (item.level or "intermediate").lower()
        exp_bonus = 0
        if experience == "beginner":
            if item_level == "beginner":
                exp_bonus = -20
            elif item_level == "advanced":
                exp_bonus = 25
        elif experience == "intermediate":
            if item_level == "intermediate":
                exp_bonus = -15
            elif item_level == "advanced":
                exp_bonus = 5
        elif experience == "advanced":
            if item_level == "advanced":
                exp_bonus = -20
            elif item_level == "beginner":
                exp_bonus = 10

        # ── RECENT TRAINING HISTORY ──
        recency_penalty = 0
        item_name_lower = (item.name or "").lower().strip()
        if item.id in yesterday_ids or item_name_lower in yesterday_names:
            recency_penalty = 35
        elif item.id in two_days_ago_ids or item_name_lower in two_days_ago_names:
            recency_penalty = 15

        if primary_muscles & yesterday_worked_muscles:
            recency_penalty += 20

        tie_breaker = zlib.crc32(f"{user.id}:{today.isoformat()}:{item.id}".encode()) % 7

        return muscle_score + split_penalty + cat_bonus + exp_bonus + recency_penalty + tie_breaker

    eligible.sort(key=_adequacy_score)
    pick = eligible[0]
    pick_mappings = mappings_by_catalog_id.get(pick.id, [])
    history_logs = _get_valid_exercise_history(session, user.id, pick, today)

    # Suggest sets, reps, duration, weight, and rest based on category, equipment, experience, and history
    sets: int | None = None
    reps: int | None = None
    duration: int | None = None
    rest_seconds: int | None = None
    suggested_weight: float | None = None
    last_perf: str | None = None
    progression_note: str | None = None

    if pick.category == "strength":
        if _is_bodyweight_prescription(pick, user_equipment):
            sets, reps, duration, rest_seconds, last_perf, progression_note = (
                _prescribe_bodyweight_strength(
                    item=pick,
                    experience=experience,
                    history_logs=history_logs,
                    today=today,
                )
            )
        else:
            sets, reps, rest_seconds, suggested_weight, last_perf, progression_note = (
                _prescribe_weighted_strength(
                    item=pick,
                    mappings=pick_mappings,
                    goal_type=goal_type,
                    experience=experience,
                    history_logs=history_logs,
                    today=today,
                )
            )
    elif pick.category == "cardio":
        duration, rest_seconds, last_perf, progression_note = _prescribe_cardio(
            item=pick,
            goal_type=goal_type,
            experience=experience,
            history_logs=history_logs,
            today=today,
        )
    elif pick.category == "flexibility":
        base_flex_dur = 15 if experience == "beginner" else (20 if experience == "intermediate" else 25)
        duration = _clamp_int(base_flex_dur, FLEXIBILITY_DURATION_BOUNDS)

    item = RecommendationItem(
        name=pick.name,
        exercise_catalog_id=pick.id,
        category=pick.category,
        sets=sets,
        reps=reps,
        weight_kg=suggested_weight,
        rest_seconds=rest_seconds,
        last_performance=last_perf,
        duration_minutes=duration,
        description=pick.description,
    )

    detail_parts = []
    if sets and reps:
        if suggested_weight is not None:
            detail_parts.append(f"{sets} sets × {reps} reps @ {suggested_weight:g} kg")
        else:
            detail_parts.append(f"{sets} sets × {reps} reps")
    if duration:
        detail_parts.append(f"{duration} minutes")
    if rest_seconds:
        detail_parts.append(f"Rest {rest_seconds}s")
    detail_str = " · ".join(detail_parts)

    # Build a context-aware reason using adequacy information
    reason = f"Based on your '{goal_type.replace('_', ' ')}' goal and {experience} experience"

    # Add muscle-group context from adequacy
    pick_primary = [m.muscle_group.replace("_", "/") for m in pick_mappings if m.role == "primary"]

    if done_today_names:
        done_str = ", ".join(list(done_today_names)[:2])
        reason += f" (already logged: {done_str})"

        # Explain WHY this exercise was chosen
        if pick_primary and needed_muscle_set:
            trained_muscles = []
            for mv in adequacy.muscle_volumes.values():
                if mv.effective_sets > 0 and mv.muscle_group in target_muscles:
                    trained_muscles.append(mv.muscle_group.replace("_", "/"))
            if trained_muscles:
                reason += f". {', '.join(trained_muscles[:2])} already received some work"
            if pick_primary:
                reason += f", but {', '.join(pick_primary)} still needs attention"
    else:
        reason += " — you haven't exercised yet today"

    if detail_str:
        reason += f". Suggested: {detail_str}."
    if progression_note:
        reason += f" {progression_note}."
    if last_perf:
        reason += f" ({last_perf})."

    return RecommendationResponse(
        has_recommendation=True,
        type="exercise",
        title="Recommended Exercise",
        reason=reason,
        items=[item],
    )


