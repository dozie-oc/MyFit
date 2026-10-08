"""
Training volume calculation and adequacy evaluation service.

This module implements the core logic for determining whether a user's
recent training is meaningful and sufficient relative to their goal.

It is entirely deterministic — no LLM, no ML model.

Architecture:

    User profile
         ↓
    Goal / experience / frequency
         ↓
    Training target estimator
         ↓
    Exercise history
         ↓
    Muscle-group mapping
         ↓
    Current session + recent training
         ↓
    Training adequacy evaluator
         ↓
    Next-action recommender

IMPORTANT HEURISTIC NOTES:
- The weekly set targets below are starting heuristics informed by
  general resistance-training guidelines.  They are NOT scientifically
  exact prescriptions.  Individual variation is enormous.
- Primary muscles receive full set credit (1.0×).
  Secondary muscles receive partial credit (0.5×).
  This is a simplification; real contribution depends on exercise
  execution, load, and individual anatomy.
- RIR-based effort weighting uses conservative cutoffs.
  When RIR is unknown (None), the set receives full credit rather
  than being penalised — we assume the user trained with reasonable
  effort unless they tell us otherwise.
"""

from datetime import date as Date, timedelta
from dataclasses import dataclass, field

from sqlmodel import Session, select

from src.models import (
    Exercise,
    ExerciseCatalogItem,
    ExerciseMuscleMapping,
    UserGoal,
)


# ──────────────────────────────────────────────────────────────────────
# CONSTANTS — Centralised so heuristics are not scattered
# ──────────────────────────────────────────────────────────────────────

# All muscle groups the system tracks for resistance training.
ALL_MUSCLE_GROUPS = [
    "chest", "back", "shoulders", "biceps", "triceps", "forearms",
    "quadriceps", "hamstrings", "glutes", "calves", "abs_core",
]

# How much a primary vs secondary muscle contributes to set volume.
# 1 set of bench press = 1.0 effective sets for chest (primary),
#                         0.5 effective sets for triceps (secondary).
PRIMARY_MUSCLE_WEIGHT = 1.0
SECONDARY_MUSCLE_WEIGHT = 0.5

# RIR-based effort multiplier for set effectiveness.
# Sets very far from failure contribute less volume signal.
# When RIR is None (unknown), we give full credit.
RIR_EFFORT_MULTIPLIERS: dict[int | None, float] = {
    None: 1.0,   # Unknown — assume reasonable effort
    0: 1.0,      # Failure — full credit
    1: 1.0,      # Very hard — full credit
    2: 1.0,      # Hard — full credit
    3: 0.9,      # Moderate-hard — slightly reduced
    4: 0.75,     # Moderate — reduced
    5: 0.6,      # Easy-moderate
    # 6+ = warm-up territory
}

# For RIR values not in the lookup, use this floor.
RIR_EFFORT_FLOOR = 0.4


def _rir_effort(rir: int | None) -> float:
    """Return the effort multiplier for a given RIR value."""
    if rir is None:
        return RIR_EFFORT_MULTIPLIERS[None]
    if rir in RIR_EFFORT_MULTIPLIERS:
        return RIR_EFFORT_MULTIPLIERS[rir]
    return RIR_EFFORT_FLOOR


# ──────────────────────────────────────────────────────────────────────
# WEEKLY SET TARGETS PER MUSCLE GROUP
#
# These are per-week minimums and maximums, intended as starting
# heuristics.  The literature generally suggests 10-20 sets/week for
# hypertrophy, but beginners grow on far less and advanced lifters
# may need more for specific muscles.
#
# The targets are adjusted by:
#   1. Goal type (muscle-focused goals have higher set targets)
#   2. Training experience (beginners need fewer sets)
#   3. Training frequency (more days = more distribution capacity)
# ──────────────────────────────────────────────────────────────────────

# Base weekly set targets: (min, max) per muscle group.
# Indexed by goal type.
GOAL_BASE_TARGETS: dict[str, tuple[float, float]] = {
    "build_muscle":     (10.0, 20.0),
    "get_stronger":     (8.0, 16.0),
    "gain_weight":      (8.0, 18.0),
    "lose_weight":      (6.0, 12.0),
    "maintain_weight":  (6.0, 12.0),
    "improve_fitness":  (6.0, 14.0),
    "improve_endurance": (4.0, 10.0),
}

# Experience multiplier applied to the base targets.
# Beginners grow on fewer sets; advanced lifters may need more.
EXPERIENCE_MULTIPLIERS: dict[str, float] = {
    "beginner": 0.6,
    "intermediate": 1.0,
    "advanced": 1.3,
}

# Maximum exercises per session before recommending "enough for today".
# This prevents the system from endlessly recommending more exercises.
# Adjusted by training days per week (fewer days → more per session).
MAX_EXERCISES_PER_SESSION: dict[int, int] = {
    1: 8,
    2: 7,
    3: 6,
    4: 5,
    5: 5,
    6: 4,
    7: 4,
}

# Maximum total sets per session before the system considers
# the session sufficient.
MAX_SETS_PER_SESSION: dict[str, int] = {
    "beginner": 12,
    "intermediate": 18,
    "advanced": 24,
}

# Movement pattern groupings for split-awareness.
# If a user has done exercises from a push pattern,
# don't suddenly recommend 5 pull exercises in the same session.
PUSH_PATTERNS = {"horizontal_push", "vertical_push"}
PULL_PATTERNS = {"horizontal_pull", "vertical_pull"}
LEG_PATTERNS = {"squat", "hinge", "lunge"}
UPPER_PATTERNS = PUSH_PATTERNS | PULL_PATTERNS | {"isolation"}
LOWER_PATTERNS = LEG_PATTERNS | {"carry"}

# Muscle groups that are "major" for each split category
UPPER_MUSCLE_GROUPS = {"chest", "back", "shoulders", "biceps", "triceps"}
LOWER_MUSCLE_GROUPS = {"quadriceps", "hamstrings", "glutes", "calves"}


# ──────────────────────────────────────────────────────────────────────
# DATA CLASSES for structured results
# ──────────────────────────────────────────────────────────────────────

@dataclass
class MuscleVolume:
    """Accumulated training volume for a single muscle group."""
    muscle_group: str
    effective_sets: float = 0.0
    raw_sets: float = 0.0
    target_min: float = 0.0
    target_max: float = 0.0

    @property
    def status(self) -> str:
        if self.effective_sets < self.target_min:
            return "undertrained"
        elif self.effective_sets <= self.target_max:
            return "adequate"
        else:
            return "high"


@dataclass
class TrainingAdequacy:
    """Complete training adequacy evaluation result."""
    overall_status: str = "insufficient"  # insufficient | adequate | high
    session_action: str = "continue_workout"  # continue_workout | workout_adequate | prioritize_next_session | rest
    muscle_volumes: dict[str, MuscleVolume] = field(default_factory=dict)
    recommended_next: list[str] = field(default_factory=list)
    summary: str = ""
    detail: str = ""
    exercises_today: int = 0
    total_sets_today: float = 0.0
    detected_split: str | None = None  # "upper" | "lower" | "full" | None


# ──────────────────────────────────────────────────────────────────────
# CORE CALCULATION FUNCTIONS
# ──────────────────────────────────────────────────────────────────────

def get_muscle_mappings(
    session: Session,
) -> dict[int, list[ExerciseMuscleMapping]]:
    """
    Load all muscle mappings from the database, indexed by catalog item ID.
    """
    all_mappings = session.exec(select(ExerciseMuscleMapping)).all()
    result: dict[int, list[ExerciseMuscleMapping]] = {}
    for m in all_mappings:
        result.setdefault(m.exercise_catalog_id, []).append(m)
    return result


def calculate_exercise_volume(
    exercise: Exercise,
    mappings_by_catalog_id: dict[int, list[ExerciseMuscleMapping]],
) -> dict[str, float]:
    """
    Calculate the effective set volume per muscle group for a single exercise.

    Returns a dict of {muscle_group: effective_sets}.

    For resistance training:
    - Uses the exercise's sets count
    - Applies primary/secondary weighting
    - Applies RIR effort multiplier

    For cardio/flexibility exercises (no muscle mappings or no sets):
    - Returns an empty dict (cardio does not contribute resistance volume)
    """
    if exercise.sets is None or exercise.sets <= 0:
        return {}

    # Look up muscle mappings for this exercise
    catalog_id = exercise.exercise_catalog_id
    if catalog_id is None:
        return {}

    mappings = mappings_by_catalog_id.get(catalog_id, [])
    if not mappings:
        return {}

    effort = _rir_effort(exercise.rir)
    result: dict[str, float] = {}

    for mapping in mappings:
        weight = PRIMARY_MUSCLE_WEIGHT if mapping.role == "primary" else SECONDARY_MUSCLE_WEIGHT
        effective = exercise.sets * weight * effort
        result[mapping.muscle_group] = result.get(mapping.muscle_group, 0.0) + effective

    return result


def calculate_weekly_targets(
    goal: UserGoal | None,
) -> dict[str, tuple[float, float]]:
    """
    Calculate weekly set targets per muscle group based on user goal
    and experience level.

    Returns {muscle_group: (target_min, target_max)}.
    """
    goal_type = (goal.goal_type or "improve_fitness").lower() if goal else "improve_fitness"
    experience = (goal.training_experience or "beginner").lower() if goal else "beginner"

    base_min, base_max = GOAL_BASE_TARGETS.get(goal_type, (6.0, 14.0))
    exp_mult = EXPERIENCE_MULTIPLIERS.get(experience, 1.0)

    targets = {}
    for mg in ALL_MUSCLE_GROUPS:
        targets[mg] = (
            round(base_min * exp_mult, 1),
            round(base_max * exp_mult, 1),
        )

    return targets


def aggregate_volume(
    exercises: list[Exercise],
    mappings_by_catalog_id: dict[int, list[ExerciseMuscleMapping]],
) -> dict[str, float]:
    """
    Aggregate effective set volume across multiple exercises.

    Returns {muscle_group: total_effective_sets}.
    """
    totals: dict[str, float] = {}
    for ex in exercises:
        vol = calculate_exercise_volume(ex, mappings_by_catalog_id)
        for mg, sets in vol.items():
            totals[mg] = totals.get(mg, 0.0) + sets
    return totals


def detect_session_split(
    exercises: list[Exercise],
    mappings_by_catalog_id: dict[int, list[ExerciseMuscleMapping]],
) -> str | None:
    """
    Detect what kind of split the current session appears to follow.

    Returns "upper", "lower", "full", or None.
    """
    muscles_hit: set[str] = set()

    for ex in exercises:
        catalog_id = ex.exercise_catalog_id
        if catalog_id is None:
            continue
        mappings = mappings_by_catalog_id.get(catalog_id, [])
        for m in mappings:
            muscles_hit.add(m.muscle_group)

    if not muscles_hit:
        return None

    has_upper = bool(muscles_hit & UPPER_MUSCLE_GROUPS)
    has_lower = bool(muscles_hit & LOWER_MUSCLE_GROUPS)

    if has_upper and has_lower:
        return "full"
    elif has_upper:
        return "upper"
    elif has_lower:
        return "lower"
    return None


# ──────────────────────────────────────────────────────────────────────
# MAIN EVALUATION FUNCTION
# ──────────────────────────────────────────────────────────────────────

def evaluate_training_adequacy(
    session: Session,
    user_id: int,
    goal: UserGoal | None,
    today: Date | None = None,
) -> TrainingAdequacy:
    """
    Evaluate the user's training adequacy for the current week.

    This is the main entry point for the training adequacy system.

    Returns a TrainingAdequacy object containing:
    - Overall status (insufficient/adequate/high)
    - Session action recommendation
    - Per-muscle-group breakdown
    - Recommended next exercises
    - Summary and detail text
    """
    if today is None:
        today = Date.today()

    # Load muscle mappings
    mappings_by_catalog_id = get_muscle_mappings(session)

    # Fetch today's exercises
    today_exercises: list[Exercise] = list(session.exec(
        select(Exercise).where(
            Exercise.user_id == user_id,
            Exercise.date == today,
            Exercise.deleted_at.is_(None),
        )
    ).all())

    # Fetch this week's exercises (Monday through today)
    monday = today - timedelta(days=today.weekday())
    week_exercises: list[Exercise] = list(session.exec(
        select(Exercise).where(
            Exercise.user_id == user_id,
            Exercise.date >= monday,
            Exercise.date <= today,
            Exercise.deleted_at.is_(None),
        )
    ).all())

    # Calculate weekly targets
    targets = calculate_weekly_targets(goal)

    # Aggregate weekly volume
    weekly_volume = aggregate_volume(week_exercises, mappings_by_catalog_id)

    # Total sets today (raw count)
    total_sets_today = sum(
        (ex.sets or 0)
        for ex in today_exercises
        if ex.sets is not None and ex.sets > 0
    )

    # Detect session split
    detected_split = detect_session_split(today_exercises, mappings_by_catalog_id)

    # Build per-muscle-group status
    muscle_volumes: dict[str, MuscleVolume] = {}
    for mg in ALL_MUSCLE_GROUPS:
        t_min, t_max = targets.get(mg, (6.0, 14.0))
        mv = MuscleVolume(
            muscle_group=mg,
            effective_sets=round(weekly_volume.get(mg, 0.0), 1),
            raw_sets=round(weekly_volume.get(mg, 0.0), 1),
            target_min=t_min,
            target_max=t_max,
        )
        muscle_volumes[mg] = mv

    # Determine overall status
    undertrained = [mv for mv in muscle_volumes.values() if mv.status == "undertrained"]
    adequate = [mv for mv in muscle_volumes.values() if mv.status == "adequate"]
    high = [mv for mv in muscle_volumes.values() if mv.status == "high"]

    if len(adequate) + len(high) >= len(ALL_MUSCLE_GROUPS) * 0.7:
        overall_status = "adequate"
    elif len(high) > len(ALL_MUSCLE_GROUPS) * 0.5:
        overall_status = "high"
    else:
        overall_status = "insufficient"

    # Determine session action
    experience = (goal.training_experience or "beginner").lower() if goal else "beginner"
    training_days = (goal.training_days_per_week or 3) if goal else 3

    max_exercises = MAX_EXERCISES_PER_SESSION.get(training_days, 5)
    max_session_sets = MAX_SETS_PER_SESSION.get(experience, 18)

    # Check if the user has trained enough days this week already
    trained_days_this_week = len({e.date for e in week_exercises})

    session_action = "continue_workout"
    if len(today_exercises) == 0:
        # No exercises today
        if trained_days_this_week >= training_days:
            session_action = "rest"
        else:
            session_action = "continue_workout"
    elif len(today_exercises) >= max_exercises or total_sets_today >= max_session_sets:
        # Session has enough work
        session_action = "workout_adequate"
    elif overall_status == "adequate" or overall_status == "high":
        # Weekly targets largely met
        if len(today_exercises) >= 2:
            session_action = "workout_adequate"
        else:
            session_action = "continue_workout"
    else:
        # More work could be done
        session_action = "continue_workout"

    # Generate recommendations for what to do next
    recommended_next = _generate_next_recommendations(
        session=session,
        goal=goal,
        today_exercises=today_exercises,
        muscle_volumes=muscle_volumes,
        detected_split=detected_split,
        mappings_by_catalog_id=mappings_by_catalog_id,
        session_action=session_action,
    )

    # Generate summary and detail text
    summary, detail = _generate_adequacy_text(
        today_exercises=today_exercises,
        muscle_volumes=muscle_volumes,
        session_action=session_action,
        detected_split=detected_split,
        recommended_next=recommended_next,
        goal=goal,
        trained_days_this_week=trained_days_this_week,
        training_days=training_days,
    )

    return TrainingAdequacy(
        overall_status=overall_status,
        session_action=session_action,
        muscle_volumes=muscle_volumes,
        recommended_next=recommended_next,
        summary=summary,
        detail=detail,
        exercises_today=len(today_exercises),
        total_sets_today=total_sets_today,
        detected_split=detected_split,
    )


def _generate_next_recommendations(
    session: Session,
    goal: UserGoal | None,
    today_exercises: list[Exercise],
    muscle_volumes: dict[str, MuscleVolume],
    detected_split: str | None,
    mappings_by_catalog_id: dict[int, list[ExerciseMuscleMapping]],
    session_action: str,
) -> list[str]:
    """
    Generate a list of recommended next exercises or actions.

    Respects the current split context — if the user is doing upper body,
    don't recommend a bunch of leg exercises mid-session.
    """
    if session_action == "rest":
        return ["Today is a good rest day. You've already hit your weekly training target."]

    if session_action == "workout_adequate":
        # Find undertrained muscles for the next session
        undertrained = sorted(
            [mv for mv in muscle_volumes.values() if mv.status == "undertrained"],
            key=lambda mv: mv.effective_sets / max(mv.target_min, 0.1),
        )
        if undertrained:
            names = [mv.muscle_group.replace("_", "/") for mv in undertrained[:3]]
            return [
                f"Good session! For your next workout, prioritize: {', '.join(names)}."
            ]
        return ["You've done enough for today. Great work!"]

    # session_action == "continue_workout"
    # Find muscles that need the most work, respecting split context
    target_muscles = _get_relevant_muscles_for_split(detected_split)

    undertrained_relevant = sorted(
        [
            mv for mv in muscle_volumes.values()
            if mv.status == "undertrained" and mv.muscle_group in target_muscles
        ],
        key=lambda mv: mv.effective_sets / max(mv.target_min, 0.1),
    )

    if not undertrained_relevant:
        # All relevant muscles for this split are trained
        return ["Your current muscle groups are well-covered. Consider finishing up or adding accessory work."]

    # Look up exercises that hit the most-needed muscles
    done_catalog_ids = {ex.exercise_catalog_id for ex in today_exercises if ex.exercise_catalog_id}
    suggestions: list[str] = []

    needed_muscles = {mv.muscle_group for mv in undertrained_relevant[:3]}

    # Find catalog exercises that target needed muscles
    for catalog_id, mappings in mappings_by_catalog_id.items():
        if catalog_id in done_catalog_ids:
            continue
        exercise_muscles = {m.muscle_group for m in mappings if m.role == "primary"}
        overlap = exercise_muscles & needed_muscles
        if overlap:
            # Get the exercise name
            catalog_item = session.get(ExerciseCatalogItem, catalog_id)
            if catalog_item and not catalog_item.is_custom:
                muscles_str = ", ".join(sorted(overlap)).replace("_", "/")
                suggestions.append(f"{catalog_item.name} (targets: {muscles_str})")
                if len(suggestions) >= 3:
                    break

    if not suggestions:
        muscle_names = [mv.muscle_group.replace("_", "/") for mv in undertrained_relevant[:3]]
        suggestions = [f"Focus on exercises for: {', '.join(muscle_names)}"]

    return suggestions


def _get_relevant_muscles_for_split(detected_split: str | None) -> set[str]:
    """
    Return the set of muscle groups that are relevant for the detected split.

    If no split is detected (first exercise of the day), return all muscles.
    """
    if detected_split == "upper":
        return UPPER_MUSCLE_GROUPS | {"abs_core", "forearms"}
    elif detected_split == "lower":
        return LOWER_MUSCLE_GROUPS | {"abs_core"}
    else:
        # Full body or unknown — all muscles are relevant
        return set(ALL_MUSCLE_GROUPS)


def _generate_adequacy_text(
    today_exercises: list[Exercise],
    muscle_volumes: dict[str, MuscleVolume],
    session_action: str,
    detected_split: str | None,
    recommended_next: list[str],
    goal: UserGoal | None,
    trained_days_this_week: int,
    training_days: int,
) -> tuple[str, str]:
    """Generate human-readable summary and detail text."""

    goal_type = (goal.goal_type or "fitness").replace("_", " ") if goal else "fitness"

    if len(today_exercises) == 0:
        if session_action == "rest":
            summary = "Rest Day"
            detail = (
                f"You've already trained {trained_days_this_week} days this week "
                f"(target: {training_days}). Take a rest day to recover."
            )
        else:
            summary = "Ready to Train"
            # Find most undertrained muscles
            undertrained = sorted(
                [mv for mv in muscle_volumes.values() if mv.status == "undertrained"],
                key=lambda mv: mv.effective_sets / max(mv.target_min, 0.1),
            )
            if undertrained:
                names = [mv.muscle_group.replace("_", "/") for mv in undertrained[:3]]
                detail = f"Based on your '{goal_type}' goal, consider focusing on: {', '.join(names)}."
            else:
                detail = f"Your training is on track for your '{goal_type}' goal."
        return summary, detail

    # Exercises logged today
    exercise_names = [e.name for e in today_exercises]

    if session_action == "workout_adequate":
        summary = "Workout Adequate"
        # Find what was well-trained
        trained_today_muscles = set()
        for mv in muscle_volumes.values():
            if mv.effective_sets > 0 and mv.status in ("adequate", "high"):
                trained_today_muscles.add(mv.muscle_group)

        if trained_today_muscles:
            trained_str = ", ".join(sorted(mg.replace("_", "/") for mg in trained_today_muscles))
            detail = f"Good work! {trained_str} received sufficient stimulus."
        else:
            detail = "You've done enough work for this session."

        # Add info about what needs attention next
        undertrained = [mv for mv in muscle_volumes.values() if mv.status == "undertrained"]
        if undertrained:
            # Pick the 2-3 most undertrained
            names = sorted(
                [mv.muscle_group.replace("_", "/") for mv in undertrained[:3]]
            )
            detail += f" Next session, prioritize: {', '.join(names)}."

    elif session_action == "continue_workout":
        summary = "Keep Going"
        # What has been done
        done_str = ", ".join(exercise_names[:3])
        if len(exercise_names) > 3:
            done_str += f" (+{len(exercise_names) - 3} more)"

        # What needs more work
        target_muscles = _get_relevant_muscles_for_split(detected_split)
        still_needed = [
            mv for mv in muscle_volumes.values()
            if mv.status == "undertrained" and mv.muscle_group in target_muscles
        ]

        if still_needed:
            needed_str = ", ".join(
                mv.muscle_group.replace("_", "/") for mv in still_needed[:3]
            )
            detail = f"Logged: {done_str}. Still needs attention: {needed_str}."
        else:
            detail = f"Logged: {done_str}. Looking good — consider a few more sets or wrap up."

    else:  # rest
        summary = "Rest Day"
        detail = "You've met your training frequency for the week. Rest and recover!"

    return summary, detail
