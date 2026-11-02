"""
Deterministic recommendation engine.

Gathers the user's goal, profile, today's meals, today's nutrition totals,
and today's exercises, then returns a single actionable recommendation
(or a no-recommendation response when nothing useful can be suggested).

No LLM, no ML model. Pure deterministic rule-based logic.
"""

from datetime import date as Date, datetime, timedelta, timezone
import zlib
from sqlmodel import Session, select

from src.models import (
    Exercise,
    ExerciseCatalogItem,
    FoodItem,
    Meal,
    User,
    UserGoal,
)
from src.schemas import RecommendationItem, RecommendationResponse
from src.services.exercise_access import visible_exercise


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


def _word_in_text(word: str, text: str) -> bool:
    """
    Return True if `word` appears as a whole token in `text`.
    Tokens are separated by any non-alphanumeric character.
    e.g. 'butter' in 'peanut butter' -> True
         'butter' in 'buttermilk'    -> False
    """
    import re
    pattern = r'(?<![\w])' + re.escape(word) + r'(?![\w])'
    return bool(re.search(pattern, text))


def _is_food_allowed(food_name: str, dietary_pref: str, avoid_list: list[str]) -> bool:
    lower = food_name.lower()
    # Avoid list: match each avoid term as a whole word/token
    for avoid in avoid_list:
        if _word_in_text(avoid.strip(), lower):
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
    avoid_str = (goal.foods_to_avoid or "").lower() if goal else ""
    avoid_list = [a.strip() for a in avoid_str.split(",") if a.strip()]

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
# EXERCISE RECOMMENDATION
# ──────────────────────────────────────────────────────────────────────

_EQUIP_SYNONYMS = {
    "dumbbells": "dumbbell",
    "machine": "machines",
    "cable": "cables",
    "band": "bands",
    "kettlebells": "kettlebell",
}


def _equipment_ok(item_equipment: str, user_equipment: set[str]) -> bool:
    if not user_equipment:
        return True
    have = {_EQUIP_SYNONYMS.get(e, e) for e in user_equipment} - {"none"}
    options = set(item_equipment.split("|"))
    return "bodyweight" in options or bool(options & have)


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

    # ── Fetch today's exercises ──────────────────────────────────
    today_exercises: list[Exercise] = session.exec(
        select(Exercise).where(
            Exercise.user_id == user.id,
            Exercise.date == today,
            Exercise.deleted_at.is_(None),
        )
    ).all()

    # ── Target calculation ──────────────────────────────────────
    cal_target, protein_target = _calculate_targets(user, goal)
    cal_remaining = max(0.0, cal_target - total_cal)
    protein_remaining = max(0.0, protein_target - total_protein)

    # ── Training adequacy evaluation ─────────────────────────────
    from src.services.training_service import evaluate_training_adequacy

    adequacy = evaluate_training_adequacy(
        session=session,
        user_id=user.id,
        goal=goal,
        today=today,
    )

    # Derive exercise completion from training adequacy
    exercise_done = adequacy.session_action in ("workout_adequate", "rest")

    # Nutrition completion: within 90% calories and 85% protein, or < 150 kcal remaining
    cal_done = total_cal >= cal_target * 0.90 or cal_remaining < 150
    protein_done = total_protein >= protein_target * 0.85
    nutrition_done = cal_done and protein_done

    # ── Explicit type request handling ─────────────────────────
    if rec_type == "exercise":
        if exercise_done:
            if adequacy.session_action == "rest":
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

    # Case 1: Both nutrition and exercise are complete
    if nutrition_done and exercise_done:
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason=(
                "You've hit your nutrition targets and completed your workout for today. "
                "Great job – you're all set!"
            ),
        )

    # Case 2: Nothing logged yet today
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

    # Case 3: Breakfast logged, but workout not completed yet
    # Natural flow: eat breakfast -> do workout!
    if "breakfast" in logged_types and not exercise_done:
        return _recommend_exercise_with_adequacy(
            session, user, goal, today_exercises, adequacy, today=today
        )

    # Case 4: Exercise done, next meal needed
    if exercise_done and not nutrition_done and cal_remaining >= MIN_CALORIE_REMAINING:
        return _recommend_meal(
            session, user, goal, today_meals, cal_remaining, protein_remaining
        )

    # Case 5: Nutrition not done, calories remain
    if not nutrition_done and cal_remaining >= MIN_CALORIE_REMAINING:
        return _recommend_meal(
            session, user, goal, today_meals, cal_remaining, protein_remaining
        )

    # Case 6: Nutrition is done, but exercise remains
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
    split context.

    Handles three distinct scenarios:
    1. No appropriate exercise available → explain clearly, NOT "workout complete"
    2. Session adequate → no more recommendations needed
    3. Session not adequate → recommend next exercise with reasoning
    """
    if today is None:
        today = Date.today()

    goal_type = (goal.goal_type if goal else None) or "improve_fitness"
    experience = (goal.training_experience or "beginner").lower() if goal else "beginner"
    equipment_str = (goal.available_equipment or "") if goal else ""
    user_equipment = {e.strip().lower() for e in equipment_str.split(",") if e.strip()}
    done_names = {e.name.lower().strip() for e in today_exercises}

    # Load visible catalog for this user
    catalog: list[ExerciseCatalogItem] = session.exec(
        select(ExerciseCatalogItem).where(*visible_exercise(user.id))
    ).all()

    if not catalog:
        # No exercises available — NOT the same as "workout complete"
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="No exercises found in the catalog. Add exercises to get recommendations.",
            items=[],
        )

    # Filter out exercises already done today and incompatible equipment
    eligible = [
        item for item in catalog
        if item.name.lower().strip() not in done_names
        and _equipment_ok(item.equipment, user_equipment)
    ]

    if not eligible:
        # No suitable exercise available — different from "workout complete"
        if done_names:
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason=(
                    "No additional compatible exercises available in the catalog. "
                    "You may have covered all available options for today."
                ),
                items=[],
            )
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="No exercises in the catalog match your available equipment.",
            items=[],
        )

    # Use training adequacy to find muscles that need work
    from src.services.training_service import (
        get_muscle_mappings,
        _get_relevant_muscles_for_split,
        CARDIO_PRIMARY_GOALS,
    )

    mappings_by_catalog_id = get_muscle_mappings(session)
    target_muscles = _get_relevant_muscles_for_split(adequacy.detected_split)

    # Find the most undertrained muscles relevant to the current split
    undertrained_muscles = sorted(
        [
            mv for mv in adequacy.muscle_volumes.values()
            if mv.status == "undertrained" and mv.muscle_group in target_muscles
        ],
        key=lambda mv: mv.effective_sets / max(mv.target_min, 0.1),
    )

    needed_muscle_set = {mv.muscle_group for mv in undertrained_muscles[:4]}

    recent_exercises = session.exec(
        select(Exercise).where(
            Exercise.user_id == user.id,
            Exercise.deleted_at.is_(None),
            Exercise.date >= today - timedelta(days=2),
            Exercise.date <= today - timedelta(days=1),
        )
    ).all()
    yesterday_ids = {
        e.exercise_catalog_id
        for e in recent_exercises
        if e.date == today - timedelta(days=1) and e.exercise_catalog_id is not None
    }
    two_days_ago_ids = {
        e.exercise_catalog_id
        for e in recent_exercises
        if e.date == today - timedelta(days=2) and e.exercise_catalog_id is not None
    }

    # Score eligible exercises: prefer those that hit needed muscles
    def _adequacy_score(item: ExerciseCatalogItem) -> float:
        """
        Lower score = better recommendation.
        Exercises that target needed muscle groups score much lower.
        """
        mappings = mappings_by_catalog_id.get(item.id, [])
        primary_muscles = {m.muscle_group for m in mappings if m.role == "primary"}
        secondary_muscles = {m.muscle_group for m in mappings if m.role == "secondary"}
        has_mappings = len(mappings) > 0

        # Primary match is worth more than secondary
        primary_overlap = primary_muscles & needed_muscle_set
        secondary_overlap = secondary_muscles & needed_muscle_set

        # Score: lower is better
        muscle_score = 100 - (len(primary_overlap) * 30 + len(secondary_overlap) * 10)

        # Prefer exercises matching goal categories
        preferred_categories = GOAL_EXERCISE_CATEGORY.get(goal_type, ["cardio", "strength"])
        cat_bonus = 0 if item.category in preferred_categories else 50

        # For cardio goals, strongly prefer cardio exercises
        if goal_type in CARDIO_PRIMARY_GOALS and item.category == "cardio":
            cat_bonus = -40

        # Penalise exercises with no muscle mappings slightly —
        # we can't guarantee they target what's needed
        if not has_mappings and item.category == "strength":
            muscle_score += 20

        # Experience-based preference using catalog level
        exp_bonus = 0
        if experience == "beginner":
            if item.level == "beginner":
                exp_bonus = -15
            elif item.level == "advanced":
                exp_bonus = 15
        elif experience == "intermediate":
            if item.level == "intermediate":
                exp_bonus = -10
        elif experience == "advanced":
            if item.level == "advanced":
                exp_bonus = -15
            elif item.level == "beginner":
                exp_bonus = 10

        recency_penalty = 0
        if item.id in yesterday_ids:
            recency_penalty = 25
        elif item.id in two_days_ago_ids:
            recency_penalty = 15

        tie_breaker = zlib.crc32(f"{user.id}:{today.isoformat()}:{item.id}".encode()) % 7

        return muscle_score + cat_bonus + exp_bonus + recency_penalty + tie_breaker

    eligible.sort(key=_adequacy_score)
    pick = eligible[0]

    # Suggest sets/reps or duration based on category and experience
    sets: int | None = None
    reps: int | None = None
    duration: int | None = None

    if pick.category == "strength":
        if experience == "beginner":
            sets, reps = 3, 10
        elif experience == "intermediate":
            sets, reps = 4, 8
        else:
            sets, reps = 5, 5
    elif pick.category == "cardio":
        if experience == "beginner":
            duration = 20
        elif experience == "intermediate":
            duration = 30
        else:
            duration = 45
    elif pick.category == "flexibility":
        duration = 20 if experience == "beginner" else 30

    item = RecommendationItem(
        name=pick.name,
        exercise_catalog_id=pick.id,
        category=pick.category,
        sets=sets,
        reps=reps,
        duration_minutes=duration,
        description=pick.description,
    )

    detail_parts = []
    if sets and reps:
        detail_parts.append(f"{sets} sets × {reps} reps")
    if duration:
        detail_parts.append(f"{duration} minutes")
    detail_str = " · ".join(detail_parts)

    # Build a context-aware reason using adequacy information
    reason = f"Based on your '{goal_type.replace('_', ' ')}' goal and {experience} experience"

    # Add muscle-group context from adequacy
    pick_mappings = mappings_by_catalog_id.get(pick.id, [])
    pick_primary = [m.muscle_group.replace("_", "/") for m in pick_mappings if m.role == "primary"]

    if done_names:
        done_str = ", ".join(list(done_names)[:2])
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

    return RecommendationResponse(
        has_recommendation=True,
        type="exercise",
        title="Recommended Exercise",
        reason=reason,
        items=[item],
    )


