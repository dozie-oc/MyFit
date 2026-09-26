"""
Deterministic recommendation engine.

Gathers the user's goal, profile, today's meals, today's nutrition totals,
and today's exercises, then returns a single actionable recommendation
(or a no-recommendation response when nothing useful can be suggested).

No LLM, no ML model. Pure deterministic rule-based logic.
"""

from datetime import date as Date, datetime, timedelta, timezone
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

# Equipment requirements per known catalog exercise
EXERCISE_EQUIPMENT_MAP: dict[str, str] = {
    # Barbell exercises
    "bench press": "barbell",
    "barbell squat": "barbell",
    "deadlift": "barbell",
    "overhead press": "barbell",
    "barbell row": "barbell",
    # Dumbbell exercises
    "dumbbell curl": "dumbbell",
    # Machine exercises
    "leg press": "machines",
    "rowing machine": "machines",
    "elliptical": "machines",
    # Bodyweight / none (compatible with any equipment)
    "push-ups": "bodyweight",
    "pull-ups": "bodyweight",
    "dips": "bodyweight",
    "plank": "bodyweight",
    "running": "bodyweight",
    "walking": "bodyweight",
    "swimming": "bodyweight",
    "jump rope": "bodyweight",
    "hiit": "bodyweight",
    "yoga": "bodyweight",
    "pilates": "bodyweight",
    "stretching": "bodyweight",
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
    for avoid in avoid_list:
        if avoid in lower:
            return False

    if dietary_pref == "vegan":
        animal_keywords = MEAT_POULTRY_KEYWORDS | SEAFOOD_KEYWORDS | DAIRY_EGG_KEYWORDS
        if any(kw in lower for kw in animal_keywords):
            return False
    elif dietary_pref == "vegetarian":
        meat_fish = MEAT_POULTRY_KEYWORDS | SEAFOOD_KEYWORDS
        if any(kw in lower for kw in meat_fish):
            return False
    elif dietary_pref == "pescatarian":
        if any(kw in lower for kw in MEAT_POULTRY_KEYWORDS):
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
        select(FoodItem).where(FoodItem.deleted_at.is_(None))
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

def _is_exercise_equipment_compatible(
    exercise_name: str,
    user_equipment_set: set[str],
) -> bool:
    """Check if an exercise is compatible with the user's available equipment."""
    if not user_equipment_set:
        return True

    lower = exercise_name.lower().strip()
    req = EXERCISE_EQUIPMENT_MAP.get(lower)

    if not req:
        if "barbell" in lower:
            req = "barbell"
        elif "dumbbell" in lower:
            req = "dumbbell"
        elif "machine" in lower or "cable" in lower:
            req = "machines"
        else:
            req = "bodyweight"

    if req == "bodyweight":
        return True

    has_barbell = "barbell" in user_equipment_set
    has_dumbbell = "dumbbell" in user_equipment_set or "dumbbells" in user_equipment_set
    has_machines = "machines" in user_equipment_set or "machine" in user_equipment_set or "cables" in user_equipment_set

    if req == "barbell" and has_barbell:
        return True
    if req == "dumbbell" and has_dumbbell:
        return True
    if req == "machines" and has_machines:
        return True

    return False


def _recommend_exercise(
    session: Session,
    user: User,
    goal: UserGoal | None,
    today_exercises: list[Exercise],
) -> RecommendationResponse:
    """
    Pick a suitable catalog exercise compatible with equipment and goal,
    excluding any exercises already logged today.
    """
    goal_type = (goal.goal_type if goal else None) or "improve_fitness"
    preferred_categories = GOAL_EXERCISE_CATEGORY.get(goal_type, ["cardio", "strength"])
    experience = (goal.training_experience or "beginner").lower() if goal else "beginner"

    equipment_str = (goal.available_equipment or "") if goal else ""
    user_equipment = {e.strip().lower() for e in equipment_str.split(",") if e.strip()}

    # Names of exercises already done today
    done_names = {e.name.lower().strip() for e in today_exercises}

    # Load full catalog
    catalog: list[ExerciseCatalogItem] = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.deleted_at.is_(None))
    ).all()

    if not catalog:
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="No exercises found in the catalog. Add exercises to get recommendations.",
            items=[],
        )

    # Filter out exercises already completed today and incompatible equipment
    eligible = [
        item for item in catalog
        if item.name.lower().strip() not in done_names
        and _is_exercise_equipment_compatible(item.name, user_equipment)
    ]

    if not eligible:
        if done_names:
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason="You've already covered all available compatible exercises for today. Great work!",
                items=[],
            )
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="No exercises in the catalog match your available equipment.",
            items=[],
        )

    # Sort eligible by preference (preferred category first)
    def _score(item: ExerciseCatalogItem) -> int:
        cat_score = preferred_categories.index(item.category) if item.category in preferred_categories else 99
        # Beginners favor bodyweight or foundational compound movements
        if experience == "beginner":
            if item.name.lower() in ("push-ups", "walking", "plank", "barbell squat", "bench press"):
                return cat_score - 10
        elif experience == "advanced":
            if item.name.lower() in ("deadlift", "running", "overhead press", "barbell row", "hiit"):
                return cat_score - 10
        return cat_score

    eligible.sort(key=_score)
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

    reason = f"Based on your '{goal_type.replace('_', ' ')}' goal and {experience} experience"
    if done_names:
        done_str = ", ".join(list(done_names)[:2])
        reason += f" (already logged: {done_str})"
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
    - Today's exercises & training days per week
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

    # ── Completion states ────────────────────────────────────────
    # Exercise completion: 1 or more logged sessions means user has exercised today
    sessions_today = len(today_exercises)
    exercise_done = sessions_today >= 1

    # Check weekly training frequency if training_days_per_week is set
    training_days = goal.training_days_per_week if goal else None
    if training_days and training_days < 7 and sessions_today == 0:
        monday = today - timedelta(days=today.weekday())
        week_exercises = session.exec(
            select(Exercise).where(
                Exercise.user_id == user.id,
                Exercise.date >= monday,
                Exercise.date <= today,
                Exercise.deleted_at.is_(None),
            )
        ).all()
        trained_days_this_week = len({e.date for e in week_exercises})
        if trained_days_this_week >= training_days:
            # User has already hit their training frequency this week on previous days!
            exercise_done = True

    # Nutrition completion: within 90% calories and 85% protein, or < 150 kcal remaining
    cal_done = total_cal >= cal_target * 0.90 or cal_remaining < 150
    protein_done = total_protein >= protein_target * 0.85
    nutrition_done = cal_done and protein_done

    # ── Explicit type request handling ─────────────────────────
    if rec_type == "exercise":
        if sessions_today >= 1:
            ex_names = ", ".join(e.name for e in today_exercises)
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason=(
                    f"You have already completed your workout today ({ex_names}). "
                    "Great work – make sure to rest and recover!"
                ),
                items=[],
            )
        if exercise_done and training_days:
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason=(
                    f"You've already trained {training_days} days this week, hitting your weekly target! "
                    "Today is a scheduled rest day."
                ),
                items=[],
            )
        return _recommend_exercise(session, user, goal, today_exercises)

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
        return _recommend_exercise(session, user, goal, today_exercises)

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
        return _recommend_exercise(session, user, goal, today_exercises)

    # Default fallback: on track
    return RecommendationResponse(
        has_recommendation=False,
        type="none",
        reason="You're on track for today – both your nutrition and workout look good!",
    )
