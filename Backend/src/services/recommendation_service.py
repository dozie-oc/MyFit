"""
Deterministic recommendation engine.

Gathers the user's goal, today's meals, today's nutrition totals,
and today's exercises, then returns a single actionable recommendation
(or a no-recommendation response when nothing useful can be suggested).

No LLM, no ML model. Pure Python rule-based logic.
"""

from datetime import date as Date, datetime, timezone
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
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

# Estimated daily calorie targets by goal type.
CALORIE_TARGETS: dict[str, int] = {
    "lose_weight": 1600,
    "gain_weight": 2800,
    "build_muscle": 2500,
    "maintain_weight": 2000,
    "improve_fitness": 2000,
    "improve_endurance": 2200,
    "get_stronger": 2500,
}

# Estimated daily protein targets (grams) by goal type.
PROTEIN_TARGETS: dict[str, int] = {
    "lose_weight": 120,
    "gain_weight": 150,
    "build_muscle": 180,
    "maintain_weight": 100,
    "improve_fitness": 120,
    "improve_endurance": 130,
    "get_stronger": 160,
}

# Default values when no goal is set.
DEFAULT_CALORIE_TARGET = 2000
DEFAULT_PROTEIN_TARGET = 100

# How close to the daily target (fraction) before we stop recommending.
CALORIE_DONE_FRACTION = 0.90
PROTEIN_DONE_FRACTION = 0.85

# Minimum remaining calories worth recommending a meal for.
MIN_CALORIE_REMAINING = 200

# Exercise categories to favour by goal.
GOAL_EXERCISE_CATEGORY: dict[str, list[str]] = {
    "lose_weight": ["cardio", "strength"],
    "gain_weight": ["strength"],
    "build_muscle": ["strength"],
    "maintain_weight": ["cardio", "strength"],
    "improve_fitness": ["cardio", "strength", "flexibility"],
    "improve_endurance": ["cardio"],
    "get_stronger": ["strength"],
}

# How many exercise sessions per day counts as "done".
MAX_DAILY_EXERCISE_SESSIONS = 4


# ──────────────────────────────────────────────────────────────────────
# NUTRITION HELPERS
# ──────────────────────────────────────────────────────────────────────

def _nutrition_per_100g(food: FoodItem, grams: float = 100.0) -> dict:
    factor = grams / 100.0
    return {
        "calories": food.calories_per_100g * factor,
        "protein": food.protein_per_100g * factor,
        "carbs": food.carbs_per_100g * factor,
        "fat": food.fat_per_100g * factor,
    }


def _meal_label_from_time() -> str:
    """
    Return the expected next meal name based on current local time.
    This is a rough heuristic – the recommendation logic is still
    driven by remaining nutrition budget, not purely by time.
    """
    hour = datetime.now().hour
    if hour < 11:
        return "breakfast"
    if hour < 15:
        return "lunch"
    if hour < 21:
        return "dinner"
    return "snack"


# ──────────────────────────────────────────────────────────────────────
# MEAL RECOMMENDATION
# ──────────────────────────────────────────────────────────────────────

def _recommend_meal(
    session: Session,
    user: User,
    goal: UserGoal | None,
    today_meals: list[Meal],
    cal_remaining: float,
    protein_remaining: float,
) -> RecommendationResponse:
    """
    Pick suitable food items from the database as a meal recommendation.

    Prioritisation:
    - Muscle gain / weight gain: high-calorie, high-protein
    - Weight loss: lean protein, low calorie
    - Everything else: balanced
    """

    goal_type = goal.goal_type if goal else None
    dietary_pref = (goal.dietary_preference or "").lower() if goal else ""
    avoid = (goal.foods_to_avoid or "").lower() if goal else ""
    avoid_list = [a.strip() for a in avoid.split(",") if a.strip()] if avoid else []

    # Load all non-deleted food items.
    foods: list[FoodItem] = session.exec(
        select(FoodItem).where(FoodItem.deleted_at.is_(None))
    ).all()

    if not foods:
        next_meal = _meal_label_from_time()
        return RecommendationResponse(
            has_recommendation=True,
            type="meal",
            title=f"Recommended {next_meal}",
            reason=(
                f"You still need approximately {int(cal_remaining)} kcal "
                f"and {int(protein_remaining)}g of protein today. "
                "Add some food items to the database to get personalised suggestions."
            ),
            items=[],
        )

    # Filter out avoided foods.
    def _is_allowed(f: FoodItem) -> bool:
        name_lower = f.name.lower()
        return not any(a in name_lower for a in avoid_list)

    foods = [f for f in foods if _is_allowed(f)]

    # Sort based on goal.
    if goal_type in ("build_muscle", "gain_weight", "get_stronger"):
        # Prioritise protein density (protein per calorie).
        foods.sort(
            key=lambda f: (
                f.protein_per_100g / max(f.calories_per_100g, 1),
                f.protein_per_100g,
            ),
            reverse=True,
        )
    elif goal_type == "lose_weight":
        # Prioritise lean foods: high protein, lower calories.
        foods.sort(
            key=lambda f: (
                f.protein_per_100g / max(f.calories_per_100g, 1),
                -f.calories_per_100g,
            ),
            reverse=True,
        )
    else:
        # Balanced: decent protein, moderate calories.
        foods.sort(
            key=lambda f: f.protein_per_100g,
            reverse=True,
        )

    # Pick up to 3 items whose combined calories fit what remains.
    budget_cal = min(cal_remaining, 800)  # cap single meal budget
    selected: list[tuple[FoodItem, float]] = []  # (food, grams)
    accumulated_cal = 0.0
    accumulated_protein = 0.0

    for food in foods[:30]:  # consider top-30 most suitable
        if len(selected) >= 3:
            break
        if food.calories_per_100g <= 0:
            continue
        # Choose a sensible serving (100–200g, or until budget hit).
        serving_g = min(200.0, (budget_cal - accumulated_cal) / food.calories_per_100g * 100)
        serving_g = max(50.0, serving_g)
        n = _nutrition_per_100g(food, serving_g)
        if accumulated_cal + n["calories"] > budget_cal + 50:
            continue
        selected.append((food, serving_g))
        accumulated_cal += n["calories"]
        accumulated_protein += n["protein"]

    next_meal = _meal_label_from_time()

    items = [
        RecommendationItem(
            name=food.name,
            calories=round(_nutrition_per_100g(food, g)["calories"], 1),
            protein=round(_nutrition_per_100g(food, g)["protein"], 1),
            carbs=round(_nutrition_per_100g(food, g)["carbs"], 1),
            fat=round(_nutrition_per_100g(food, g)["fat"], 1),
            description=f"{int(g)}g serving",
        )
        for food, g in selected
    ]

    reason = (
        f"You still need approximately {int(cal_remaining)} kcal "
        f"and {int(protein_remaining)}g of protein today."
    )
    if goal_type in ("build_muscle", "gain_weight"):
        reason += " Focus on protein-rich foods to support your goal."
    elif goal_type == "lose_weight":
        reason += " These lean options keep you within your calorie budget."

    return RecommendationResponse(
        has_recommendation=True,
        type="meal",
        title=f"Recommended {next_meal}",
        reason=reason,
        items=items,
    )


# ──────────────────────────────────────────────────────────────────────
# EXERCISE RECOMMENDATION
# ──────────────────────────────────────────────────────────────────────

def _recommend_exercise(
    session: Session,
    user: User,
    goal: UserGoal | None,
    today_exercises: list[Exercise],
) -> RecommendationResponse:
    """
    Pick a catalog exercise the user hasn't done today.

    Selection logic:
    1. Determine which categories to recommend based on goal.
    2. Exclude any exercises the user has already logged today.
    3. Return the first suitable exercise from the catalog.
    """

    goal_type = (goal.goal_type if goal else None) or "improve_fitness"
    preferred_categories = GOAL_EXERCISE_CATEGORY.get(goal_type, ["cardio", "strength"])
    experience = (goal.training_experience or "beginner") if goal else "beginner"
    equipment_str = (goal.available_equipment or "") if goal else ""
    equipment = [e.strip().lower() for e in equipment_str.split(",") if e.strip()]

    # Names (lowercase) of exercises already done today.
    done_names = {e.name.lower() for e in today_exercises}

    # Load entire catalog.
    catalog: list[ExerciseCatalogItem] = session.exec(
        select(ExerciseCatalogItem).where(
            ExerciseCatalogItem.deleted_at.is_(None)
        )
    ).all()

    # Filter by preferred category first, then fall back.
    def _score(item: ExerciseCatalogItem) -> int:
        if item.name.lower() in done_names:
            return -1  # already done, skip
        cat_score = preferred_categories.index(item.category) if item.category in preferred_categories else 99
        return cat_score

    eligible = [c for c in catalog if c.name.lower() not in done_names]
    if not catalog:
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="No exercises found in the catalog. Add exercises to get recommendations.",
            items=[],
        )
    if not eligible:
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason="You've already covered all catalog exercises today. Great work!",
            items=[],
        )

    # Sort by category preference.
    eligible.sort(key=_score)

    # Filter to preferred categories; if empty fall back to all.
    preferred = [c for c in eligible if c.category in preferred_categories]
    candidates = preferred if preferred else eligible

    pick = candidates[0]

    # Suggest sets/reps or duration based on category and experience.
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
        duration = 20

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

    reason = f"Based on your '{goal_type.replace('_', ' ')}' goal"
    if done_names:
        done_str = ", ".join(list(done_names)[:3])
        reason += f". You've already done: {done_str}."
    else:
        reason += ". You haven't exercised yet today."
    if detail_str:
        reason += f" Suggested: {detail_str}."

    return RecommendationResponse(
        has_recommendation=True,
        type="exercise",
        title="Recommended exercise",
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
    Main entry point.

    Gathers context, applies rules, and returns a recommendation.
    If rec_type is specified ('meal' or 'exercise'), returns a recommendation
    specifically for that category.
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

    # ── Compute today's nutrition totals ────────────────────────
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

    # ── Resolve targets ─────────────────────────────────────────
    goal_type = (goal.goal_type if goal else None) or "maintain_weight"
    cal_target = CALORIE_TARGETS.get(goal_type, DEFAULT_CALORIE_TARGET)
    protein_target = PROTEIN_TARGETS.get(goal_type, DEFAULT_PROTEIN_TARGET)

    # Adjust for body weight (rough BMR-based scaling).
    weight_kg = user.weight or 70.0
    if weight_kg > 0:
        scale = weight_kg / 70.0
        cal_target = int(cal_target * max(0.7, min(scale, 1.5)))
        protein_target = int(protein_target * max(0.7, min(scale, 1.5)))

    cal_remaining = cal_target - total_cal
    protein_remaining = protein_target - total_protein

    # ── Rule: Evaluate completion states ────────────────────────
    sessions_today = len(today_exercises)
    max_sessions = MAX_DAILY_EXERCISE_SESSIONS

    cal_done = total_cal >= cal_target * CALORIE_DONE_FRACTION
    protein_done = total_protein >= protein_target * PROTEIN_DONE_FRACTION
    nutrition_done = cal_done and protein_done
    exercise_done = sessions_today >= max_sessions

    # ── Explicit type request handling ─────────────────────────
    if rec_type == "exercise":
        if exercise_done:
            return RecommendationResponse(
                has_recommendation=False,
                type="none",
                reason=(
                    f"You have already completed {sessions_today} exercise sessions today. "
                    "Great work – make sure to rest and recover!"
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
    # If both nutrition and exercise are complete:
    if nutrition_done and exercise_done:
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason=(
                "You've hit your nutrition targets and completed your workout for today. "
                "Great job – enjoy the rest of your day!"
            ),
        )

    hour = datetime.now().hour

    # Late night wind-down (after 21:00):
    if hour >= 21 and total_cal >= cal_target * 0.80:
        if not exercise_done:
            return _recommend_exercise(session, user, goal, today_exercises)
        return RecommendationResponse(
            has_recommendation=False,
            type="none",
            reason=(
                "You're close to your daily calorie target for today. "
                "Consider winding down and getting good sleep."
            ),
        )

    # Prioritize exercise if no workout has been done today:
    # Especially for workout-focused goals, or if breakfast/lunch has been had,
    # or if it's mid-day.
    is_training_goal = goal_type in (
        "build_muscle",
        "get_stronger",
        "improve_endurance",
        "improve_fitness",
    )

    if not exercise_done:
        if sessions_today == 0:
            # If user has logged at least one meal, workout is naturally next
            if len(today_meals) > 0:
                return _recommend_exercise(session, user, goal, today_exercises)
            # If it's daytime (10:00 - 20:00) and user has a training-focused goal
            if is_training_goal and hour >= 10:
                return _recommend_exercise(session, user, goal, today_exercises)

    # If nutrition not done and calories remain, recommend meal
    if not nutrition_done and cal_remaining >= MIN_CALORIE_REMAINING:
        return _recommend_meal(
            session, user, goal, today_meals, cal_remaining, protein_remaining
        )

    # If nutrition is done, but exercise remains
    if not exercise_done:
        return _recommend_exercise(session, user, goal, today_exercises)

    # Default: everything looks good
    return RecommendationResponse(
        has_recommendation=False,
        type="none",
        reason="You're on track for today – both your nutrition and workout look good!",
    )
