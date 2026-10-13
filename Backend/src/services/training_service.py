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
    Muscle-group mapping + Cardio evaluation
         ↓
    Session adequacy  ←──→  Weekly progress
         ↓                        ↓
    Next-action recommender
         ↓
    Structured result

TWO SEPARATE QUESTIONS:
  1. Session adequacy: Has the user completed a reasonable amount of
     goal-appropriate work in the current workout?
  2. Weekly progress: How is the user progressing toward their broader
     training-frequency and muscle-group targets?

These signals inform one another but are NOT interchangeable.

IMPORTANT HEURISTIC NOTES:
- The weekly set targets below are starting heuristics informed by
  general resistance-training guidelines.  They are NOT scientifically
  exact prescriptions.  Individual variation is enormous.
- Primary muscles receive full set credit (1.0×).
  Secondary muscles receive partial credit (0.5×).
- RIR-based effort weighting uses conservative cutoffs.
  When RIR is unknown (None), the set receives full credit rather
  than being penalised — we assume the user trained with reasonable
  effort unless they tell us otherwise.
- Cardio adequacy is evaluated using duration, distance, and
  intensity — NOT strength-training set counts.
"""

from datetime import date as Date, timedelta
from dataclasses import dataclass, field

from sqlmodel import Session, select

from src.models import (
    Exercise,
    ExerciseCatalogItem,
    ExerciseMuscleMapping,
    UserGoal,
    WorkoutSession,
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

# ──────────────────────────────────────────────────────────────────────
# CARDIO ADEQUACY TARGETS (duration-based, per-session)
#
# Cardio uses duration/distance/intensity — NOT set counts.
# ──────────────────────────────────────────────────────────────────────

# Minimum minutes for a cardio session to be considered meaningful.
CARDIO_MIN_DURATION: dict[str, int] = {
    "beginner": 15,
    "intermediate": 20,
    "advanced": 25,
}

# Target minutes for a good cardio session.
CARDIO_TARGET_DURATION: dict[str, int] = {
    "beginner": 25,
    "intermediate": 35,
    "advanced": 45,
}

# Intensity multiplier for cardio effort.
CARDIO_INTENSITY_MULTIPLIERS: dict[str, float] = {
    "low": 0.7,
    "moderate": 1.0,
    "high": 1.3,
}

# Goals that should be evaluated primarily/partially via cardio.
CARDIO_PRIMARY_GOALS = {"improve_endurance"}
CARDIO_SECONDARY_GOALS = {"lose_weight", "improve_fitness", "maintain_weight"}
STRENGTH_PRIMARY_GOALS = {"build_muscle", "get_stronger", "gain_weight"}

# ──────────────────────────────────────────────────────────────────────
# SESSION-LEVEL CAPS (safety thresholds, not sole adequacy criteria)
# ──────────────────────────────────────────────────────────────────────

# Maximum total effective sets per session before suggesting "enough."
# These serve as an upper safety bound, NOT the primary adequacy test.
MAX_SETS_PER_SESSION: dict[str, int] = {
    "beginner": 15,
    "intermediate": 22,
    "advanced": 30,
}

# Movement pattern groupings for split-awareness.
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
class CardioStatus:
    """Cardio session adequacy for a single day."""
    total_duration_minutes: float = 0.0
    effective_duration_minutes: float = 0.0  # adjusted by intensity
    target_minutes: float = 30.0
    min_minutes: float = 15.0
    has_meaningful_cardio: bool = False
    # Percentage of target achieved (0.0 to 1.0+)
    completion_ratio: float = 0.0


@dataclass
class SessionAdequacy:
    """
    Answers: has this SINGLE SESSION been sufficient?

    Separate from weekly progress.
    """
    is_adequate: bool = False
    # How confident are we? (low = missing data, medium = partial,
    # high = clear evidence)
    confidence: str = "low"  # "low" | "medium" | "high"
    reason: str = ""
    # Which categories of work contributed to this assessment
    has_strength_work: bool = False
    has_cardio_work: bool = False
    strength_sets_done: float = 0.0
    muscle_groups_hit: int = 0
    cardio_status: CardioStatus = field(default_factory=CardioStatus)


@dataclass
class WeeklyProgress:
    """
    Answers: how is the user progressing across the whole week?

    Separate from session adequacy.
    """
    muscle_volumes: dict[str, MuscleVolume] = field(default_factory=dict)
    overall_status: str = "insufficient"  # insufficient | adequate | high
    trained_days_this_week: int = 0
    training_days_target: int = 3
    is_rest_day_eligible: bool = False


@dataclass
class TrainingAdequacy:
    """Complete training adequacy evaluation result."""
    overall_status: str = "insufficient"  # insufficient | adequate | high
    session_action: str = "continue_workout"  # continue_workout | workout_adequate | rest
    muscle_volumes: dict[str, MuscleVolume] = field(default_factory=dict)
    recommended_next: list[str] = field(default_factory=list)
    summary: str = ""
    detail: str = ""
    exercises_today: int = 0
    total_sets_today: float = 0.0
    detected_split: str | None = None  # "upper" | "lower" | "full" | None
    # New: separated sub-evaluations
    session_adequacy: SessionAdequacy = field(default_factory=SessionAdequacy)
    weekly_progress: WeeklyProgress = field(default_factory=WeeklyProgress)


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
# CARDIO EVALUATION
# ──────────────────────────────────────────────────────────────────────

def evaluate_cardio_session(
    exercises: list[Exercise],
    experience: str,
) -> CardioStatus:
    """
    Evaluate cardio adequacy for a set of exercises using duration,
    distance, and intensity — NOT strength-training set counts.

    Only considers exercises categorised as "cardio".
    """
    target = CARDIO_TARGET_DURATION.get(experience, 30)
    minimum = CARDIO_MIN_DURATION.get(experience, 15)

    status = CardioStatus(
        target_minutes=float(target),
        min_minutes=float(minimum),
    )

    cardio_exercises = [e for e in exercises if (e.category or "").lower() == "cardio"]

    if not cardio_exercises:
        return status

    total_raw = 0.0
    total_effective = 0.0

    for ex in cardio_exercises:
        duration = ex.duration_minutes or 0
        if duration <= 0:
            # Cardio with no duration — we cannot evaluate, but don't
            # ignore it entirely. Give minimal credit.
            duration = 5  # assume at least 5 minutes if they logged it

        intensity = (ex.intensity or "moderate").lower()
        multiplier = CARDIO_INTENSITY_MULTIPLIERS.get(intensity, 1.0)

        # Distance bonus: if they logged distance, give a small boost
        # for longer-distance sessions.
        distance_bonus = 0.0
        if ex.distance_km and ex.distance_km > 0:
            # e.g. 5km adds ~5 effective minutes worth of credit
            distance_bonus = min(ex.distance_km * 1.0, 10.0)

        raw = float(duration)
        effective = raw * multiplier + distance_bonus

        total_raw += raw
        total_effective += effective

    status.total_duration_minutes = round(total_raw, 1)
    status.effective_duration_minutes = round(total_effective, 1)
    status.has_meaningful_cardio = total_effective >= minimum
    status.completion_ratio = round(total_effective / max(target, 1.0), 2)

    return status


# ──────────────────────────────────────────────────────────────────────
# SESSION ADEQUACY (today's workout only)
# ──────────────────────────────────────────────────────────────────────

def evaluate_session_adequacy(
    exercises: list[Exercise],
    goal: UserGoal | None,
    mappings_by_catalog_id: dict[int, list[ExerciseMuscleMapping]],
) -> SessionAdequacy:
    """
    Evaluate whether the CURRENT SESSION has sufficient work.

    This is INDEPENDENT of weekly progress. A session can be adequate
    even when weekly targets are not yet met, and vice versa.

    The evaluation is goal-aware:
    - Strength goals: evaluate by working sets, muscle coverage, effort
    - Cardio goals: evaluate by duration, intensity, distance
    - Mixed goals: evaluate both dimensions
    """
    if not exercises:
        return SessionAdequacy(
            is_adequate=False,
            confidence="high",
            reason="No exercises logged yet.",
        )

    goal_type = (goal.goal_type or "improve_fitness").lower() if goal else "improve_fitness"
    experience = (goal.training_experience or "beginner").lower() if goal else "beginner"

    # Split exercises by category
    strength_exercises = [
        e for e in exercises
        if (e.category or "").lower() in ("strength", "other")
        and e.sets is not None and e.sets > 0
    ]
    cardio_exercises = [
        e for e in exercises
        if (e.category or "").lower() == "cardio"
    ]
    other_exercises = [
        e for e in exercises
        if (e.category or "").lower() not in ("strength", "cardio", "other")
        or ((e.category or "").lower() in ("strength", "other") and (e.sets is None or e.sets <= 0))
    ]

    # Calculate strength metrics for this session
    session_volume = aggregate_volume(strength_exercises, mappings_by_catalog_id)
    total_effective_sets = sum(session_volume.values())
    muscle_groups_hit = len([mg for mg, v in session_volume.items() if v > 0])

    # Count exercises with missing mappings
    unmapped_strength = sum(
        1 for e in strength_exercises
        if e.exercise_catalog_id is None
        or not mappings_by_catalog_id.get(e.exercise_catalog_id, [])
    )
    total_raw_sets = sum(e.sets or 0 for e in strength_exercises)

    # Evaluate cardio
    cardio_status = evaluate_cardio_session(exercises, experience)

    has_strength = len(strength_exercises) > 0
    has_cardio = cardio_status.has_meaningful_cardio

    # Determine adequacy based on goal type
    is_adequate = False
    confidence = "medium"
    reason_parts = []

    max_session_sets = MAX_SETS_PER_SESSION.get(experience, 22)

    if goal_type in STRENGTH_PRIMARY_GOALS:
        # Strength-focused evaluation
        is_adequate, confidence, reason_parts = _evaluate_strength_session(
            total_effective_sets=total_effective_sets,
            total_raw_sets=total_raw_sets,
            muscle_groups_hit=muscle_groups_hit,
            unmapped_strength=unmapped_strength,
            max_session_sets=max_session_sets,
            experience=experience,
            strength_exercises=strength_exercises,
        )
        # Cardio adds value but doesn't define adequacy for strength goals
        if has_cardio and not is_adequate:
            reason_parts.append(
                f"Cardio: {cardio_status.total_duration_minutes:.0f}min (good, but strength work is primary for your goal)."
            )

    elif goal_type in CARDIO_PRIMARY_GOALS:
        # Cardio-focused evaluation — NOT using set counts
        is_adequate, confidence, reason_parts = _evaluate_cardio_session_adequacy(
            cardio_status=cardio_status,
            experience=experience,
        )
        # Strength adds value but doesn't define adequacy for cardio goals
        if has_strength and not is_adequate:
            reason_parts.append(
                f"Strength: {total_effective_sets:.1f} effective sets logged — good supplementary work."
            )

    else:
        # Mixed goals (improve_fitness, lose_weight, maintain_weight)
        is_adequate, confidence, reason_parts = _evaluate_mixed_session(
            total_effective_sets=total_effective_sets,
            total_raw_sets=total_raw_sets,
            muscle_groups_hit=muscle_groups_hit,
            unmapped_strength=unmapped_strength,
            max_session_sets=max_session_sets,
            experience=experience,
            cardio_status=cardio_status,
            has_strength=has_strength,
            has_cardio=has_cardio,
            strength_exercises=strength_exercises,
        )

    # If exercises exist with no sets and no duration, lower confidence
    if other_exercises and not has_strength and not has_cardio:
        confidence = "low"
        reason_parts.append(
            f"{len(other_exercises)} exercise(s) logged without clear sets or duration — "
            "unable to fully evaluate the session."
        )

    return SessionAdequacy(
        is_adequate=is_adequate,
        confidence=confidence,
        reason=" ".join(reason_parts),
        has_strength_work=has_strength,
        has_cardio_work=has_cardio,
        strength_sets_done=total_effective_sets,
        muscle_groups_hit=muscle_groups_hit,
        cardio_status=cardio_status,
    )


MIN_DISTINCT_STRENGTH_EXERCISES = 2


def _distinct_exercise_count(exercises: list[Exercise]) -> int:
    """Number of distinct exercises (by catalog id, falling back to name)."""
    keys = set()
    for ex in exercises:
        cat_id = getattr(ex, "exercise_catalog_id", None)
        keys.add(cat_id if cat_id else (ex.name or "").strip().lower())
    return len(keys)


def _evaluate_strength_session(
    total_effective_sets: float,
    total_raw_sets: float,
    muscle_groups_hit: int,
    unmapped_strength: int,
    max_session_sets: int,
    experience: str,
    strength_exercises: list[Exercise],
) -> tuple[bool, str, list[str]]:
    """Evaluate whether a strength-focused session is adequate."""
    reason_parts: list[str] = []
    confidence = "medium"
    distinct_exercises = _distinct_exercise_count(strength_exercises)
    enough_variety = distinct_exercises >= MIN_DISTINCT_STRENGTH_EXERCISES

    # Minimum thresholds for a session (NOT weekly targets)
    # These are deliberately lower than weekly targets — a single session
    # doesn't need to satisfy the entire week.
    if experience == "beginner":
        min_effective_sets = 6.0
        min_muscle_groups = 2
    elif experience == "intermediate":
        min_effective_sets = 8.0
        min_muscle_groups = 2
    else:
        min_effective_sets = 10.0
        min_muscle_groups = 2

    # Hit the safety cap? Definitely adequate.
    if total_effective_sets >= max_session_sets:
        return True, "high", [
            f"{total_effective_sets:.0f} effective sets across {muscle_groups_hit} muscle groups — "
            "you've done substantial work this session."
        ]

    # Enough effective sets AND enough muscle group spread?
    if (
        total_effective_sets >= min_effective_sets
        and muscle_groups_hit >= min_muscle_groups
        and enough_variety
    ):
        confidence = "high" if unmapped_strength == 0 else "medium"
        reason_parts.append(
            f"{total_effective_sets:.0f} effective sets across {muscle_groups_hit} muscle groups — "
            "session is looking solid."
        )
        return True, confidence, reason_parts

    # Handle the case where exercises have no muscle mappings
    # but the raw set count is reasonable
    if unmapped_strength > 0 and total_raw_sets >= min_effective_sets:
        confidence = "low"
        reason_parts.append(
            f"{total_raw_sets} raw sets logged, but {unmapped_strength} exercise(s) "
            "have no muscle-group data — session may be adequate but cannot be confirmed."
        )
        # Be lenient: if raw sets are well above threshold, accept it
        if total_raw_sets >= min_effective_sets * 1.5 and enough_variety:
            return True, confidence, reason_parts
        return False, confidence, reason_parts

    # Volume is there but it all came from a single exercise —
    # secondary-muscle credit alone shouldn't complete a session.
    if total_effective_sets >= min_effective_sets and not enough_variety:
        reason_parts.append(
            f"{total_effective_sets:.0f} effective sets so far, but from only one exercise — "
            f"add at least one more exercise to round out the session."
        )
        return False, confidence, reason_parts

    # Not enough work yet
    if total_effective_sets > 0:
        reason_parts.append(
            f"{total_effective_sets:.0f} effective sets across {muscle_groups_hit} muscle group(s) so far — "
            f"aim for at least {min_effective_sets:.0f} sets."
        )
    else:
        if strength_exercises:
            reason_parts.append(
                f"{len(strength_exercises)} exercise(s) logged but no effective volume tracked "
                "(missing muscle mappings or sets)."
            )
        else:
            reason_parts.append("No strength exercises logged yet for your strength-focused goal.")

    return False, confidence, reason_parts


def _evaluate_cardio_session_adequacy(
    cardio_status: CardioStatus,
    experience: str,
) -> tuple[bool, str, list[str]]:
    """Evaluate whether a cardio-focused session is adequate."""
    reason_parts: list[str] = []

    if not cardio_status.has_meaningful_cardio:
        if cardio_status.total_duration_minutes > 0:
            reason_parts.append(
                f"{cardio_status.total_duration_minutes:.0f}min of cardio logged, "
                f"but the minimum for a meaningful session is {cardio_status.min_minutes:.0f}min."
            )
        else:
            reason_parts.append("No cardio logged yet for your endurance goal.")
        return False, "medium", reason_parts

    # Meaningful cardio exists — check against target
    if cardio_status.completion_ratio >= 0.85:
        reason_parts.append(
            f"{cardio_status.effective_duration_minutes:.0f} effective minutes of cardio "
            f"(target: {cardio_status.target_minutes:.0f}min) — great session."
        )
        return True, "high", reason_parts
    elif cardio_status.completion_ratio >= 0.6:
        reason_parts.append(
            f"{cardio_status.effective_duration_minutes:.0f} effective minutes of cardio "
            f"(target: {cardio_status.target_minutes:.0f}min) — decent effort, consider continuing."
        )
        return False, "medium", reason_parts
    else:
        reason_parts.append(
            f"{cardio_status.effective_duration_minutes:.0f} effective minutes of cardio "
            f"(target: {cardio_status.target_minutes:.0f}min) — keep going for a fuller session."
        )
        return False, "medium", reason_parts


def _evaluate_mixed_session(
    total_effective_sets: float,
    total_raw_sets: float,
    muscle_groups_hit: int,
    unmapped_strength: int,
    max_session_sets: int,
    experience: str,
    cardio_status: CardioStatus,
    has_strength: bool,
    has_cardio: bool,
    strength_exercises: list[Exercise],
) -> tuple[bool, str, list[str]]:
    """
    Evaluate a session for mixed goals (fitness, weight loss, maintenance).

    Either strength OR cardio work can contribute to adequacy.
    Both together is even better.
    """
    reason_parts: list[str] = []

    # Lower thresholds for mixed goals — the user doesn't need
    # a full powerlifting session or a full cardio session.
    if experience == "beginner":
        min_sets = 4.0
        min_cardio_ratio = 0.6
    elif experience == "intermediate":
        min_sets = 6.0
        min_cardio_ratio = 0.65
    else:
        min_sets = 8.0
        min_cardio_ratio = 0.7

    enough_variety = _distinct_exercise_count(strength_exercises) >= MIN_DISTINCT_STRENGTH_EXERCISES
    strength_adequate = (
        total_effective_sets >= min_sets and muscle_groups_hit >= 2 and enough_variety
    )
    cardio_adequate = cardio_status.completion_ratio >= min_cardio_ratio

    # Combined work — both contribute
    if has_strength and has_cardio:
        if strength_adequate or cardio_adequate:
            parts = []
            if has_strength:
                parts.append(f"{total_effective_sets:.0f} sets")
            if has_cardio:
                parts.append(f"{cardio_status.effective_duration_minutes:.0f}min cardio")
            reason_parts.append(
                f"Mixed session: {' + '.join(parts)} — well-rounded workout."
            )
            return True, "high", reason_parts
        else:
            parts = []
            if has_strength:
                parts.append(f"{total_effective_sets:.0f} effective sets")
            if has_cardio:
                parts.append(f"{cardio_status.effective_duration_minutes:.0f}min cardio")
            reason_parts.append(
                f"Mixed session: {' + '.join(parts)} — consider adding a bit more work."
            )
            return False, "medium", reason_parts

    # Strength only
    if has_strength:
        if total_effective_sets >= max_session_sets:
            reason_parts.append(f"{total_effective_sets:.0f} effective sets — substantial session.")
            return True, "high", reason_parts
        if strength_adequate:
            reason_parts.append(
                f"{total_effective_sets:.0f} effective sets across {muscle_groups_hit} muscle groups."
            )
            return True, "medium" if unmapped_strength > 0 else "high", reason_parts
        # Handle unmapped exercises
        if unmapped_strength > 0 and total_raw_sets >= min_sets:
            reason_parts.append(
                f"{total_raw_sets} raw sets but {unmapped_strength} unmapped exercise(s)."
            )
            if total_raw_sets >= min_sets * 1.5 and enough_variety:
                return True, "low", reason_parts
        if total_effective_sets > 0:
            reason_parts.append(
                f"{total_effective_sets:.0f} effective sets so far — aim for {min_sets:.0f}+."
            )
        else:
            reason_parts.append("Strength exercises logged but no effective volume tracked.")
        return False, "medium" if total_effective_sets > 0 else "low", reason_parts

    # Cardio only
    if has_cardio:
        if cardio_adequate:
            reason_parts.append(
                f"{cardio_status.effective_duration_minutes:.0f}min of cardio — solid session."
            )
            return True, "high", reason_parts
        reason_parts.append(
            f"{cardio_status.effective_duration_minutes:.0f}min of cardio "
            f"(target: {cardio_status.target_minutes:.0f}min)."
        )
        return False, "medium", reason_parts

    # Nothing meaningful
    reason_parts.append("No meaningful strength or cardio work detected yet.")
    return False, "low", reason_parts


# ──────────────────────────────────────────────────────────────────────
# WEEKLY PROGRESS EVALUATION
# ──────────────────────────────────────────────────────────────────────

def evaluate_weekly_progress(
    week_exercises: list[Exercise],
    goal: UserGoal | None,
    mappings_by_catalog_id: dict[int, list[ExerciseMuscleMapping]],
    today: Date,
) -> WeeklyProgress:
    """
    Evaluate the user's weekly training progress.

    This is SEPARATE from session adequacy. Weekly progress tracks
    cumulative muscle-group volume and training frequency across
    the whole week.
    """
    targets = calculate_weekly_targets(goal)
    weekly_volume = aggregate_volume(week_exercises, mappings_by_catalog_id)
    training_days = (goal.training_days_per_week or 3) if goal else 3
    trained_days = len({e.date for e in week_exercises})

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
    adequate_count = sum(1 for mv in muscle_volumes.values() if mv.status in ("adequate", "high"))
    high_count = sum(1 for mv in muscle_volumes.values() if mv.status == "high")
    total = len(ALL_MUSCLE_GROUPS)

    if adequate_count >= total * 0.7:
        overall_status = "adequate"
    elif high_count > total * 0.5:
        overall_status = "high"
    else:
        overall_status = "insufficient"

    # Is it reasonable to suggest a rest day?
    is_rest_eligible = trained_days >= training_days

    return WeeklyProgress(
        muscle_volumes=muscle_volumes,
        overall_status=overall_status,
        trained_days_this_week=trained_days,
        training_days_target=training_days,
        is_rest_day_eligible=is_rest_eligible,
    )


# ──────────────────────────────────────────────────────────────────────
# SESSION GROUPING
# ──────────────────────────────────────────────────────────────────────

def get_current_session_exercises(
    session: Session,
    user_id: int,
    today: Date,
) -> list[Exercise]:
    """
    Get exercises for the user's current workout session.

    Uses WorkoutSession grouping when an active/completed session
    exists. Falls back to date-based grouping otherwise.

    Abandoned sessions are NOT included — their exercises are excluded
    from the current session evaluation (though they remain in the DB
    for history).
    """
    # Check for an active or completed workout session today
    active_session: WorkoutSession | None = session.exec(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.date == today,
            WorkoutSession.status.in_(["active", "completed"]),
        )
    ).first()

    if active_session:
        # Use session-based grouping: only exercises linked to this session
        exercises = list(session.exec(
            select(Exercise).where(
                Exercise.user_id == user_id,
                Exercise.workout_session_id == active_session.id,
                Exercise.deleted_at.is_(None),
            )
        ).all())

        # Also include today's exercises with no session ID
        # (backward compatibility with exercises logged before sessions existed)
        unlinked = list(session.exec(
            select(Exercise).where(
                Exercise.user_id == user_id,
                Exercise.date == today,
                Exercise.workout_session_id.is_(None),
                Exercise.deleted_at.is_(None),
            )
        ).all())

        return exercises + unlinked

    # No explicit session — fall back to date-based grouping,
    # but exclude exercises linked to abandoned sessions.
    abandoned_session_ids: list[int] = [
        ws.id for ws in session.exec(
            select(WorkoutSession).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.date == today,
                WorkoutSession.status == "abandoned",
            )
        ).all()
    ]

    query = select(Exercise).where(
        Exercise.user_id == user_id,
        Exercise.date == today,
        Exercise.deleted_at.is_(None),
    )

    if abandoned_session_ids:
        # Exclude exercises from abandoned sessions
        query = query.where(
            ~Exercise.workout_session_id.in_(abandoned_session_ids)
            | Exercise.workout_session_id.is_(None)
        )

    return list(session.exec(query).all())


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
    Evaluate the user's training adequacy.

    This is the main entry point. It answers TWO separate questions:
    1. Session adequacy: Is today's workout sufficient?
    2. Weekly progress: How is the user progressing this week?

    Then combines them into an actionable session_action recommendation.
    """
    if today is None:
        today = Date.today()

    # Load muscle mappings
    mappings_by_catalog_id = get_muscle_mappings(session)

    # Get current session exercises (respects WorkoutSession grouping)
    today_exercises = get_current_session_exercises(session, user_id, today)

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

    # Total raw sets today
    total_sets_today = sum(
        (ex.sets or 0)
        for ex in today_exercises
        if ex.sets is not None and ex.sets > 0
    )

    # Detect session split
    detected_split = detect_session_split(today_exercises, mappings_by_catalog_id)

    # ── EVALUATE SESSION ADEQUACY (today's workout) ──────────────
    sess_adequacy = evaluate_session_adequacy(
        exercises=today_exercises,
        goal=goal,
        mappings_by_catalog_id=mappings_by_catalog_id,
    )

    # ── EVALUATE WEEKLY PROGRESS ─────────────────────────────────
    weekly = evaluate_weekly_progress(
        week_exercises=week_exercises,
        goal=goal,
        mappings_by_catalog_id=mappings_by_catalog_id,
        today=today,
    )

    # ── COMBINE INTO SESSION ACTION ──────────────────────────────
    # These two evaluations inform each other but are NOT equivalent.
    session_action = _determine_session_action(
        session_adequacy=sess_adequacy,
        weekly_progress=weekly,
        exercises_today=today_exercises,
    )

    # Generate recommendations for what to do next
    recommended_next = _generate_next_recommendations(
        session=session,
        goal=goal,
        today_exercises=today_exercises,
        muscle_volumes=weekly.muscle_volumes,
        detected_split=detected_split,
        mappings_by_catalog_id=mappings_by_catalog_id,
        session_action=session_action,
    )

    # Generate summary and detail text
    summary, detail = _generate_adequacy_text(
        today_exercises=today_exercises,
        session_adequacy=sess_adequacy,
        weekly_progress=weekly,
        session_action=session_action,
        detected_split=detected_split,
        recommended_next=recommended_next,
        goal=goal,
    )

    return TrainingAdequacy(
        overall_status=weekly.overall_status,
        session_action=session_action,
        muscle_volumes=weekly.muscle_volumes,
        recommended_next=recommended_next,
        summary=summary,
        detail=detail,
        exercises_today=len(today_exercises),
        total_sets_today=total_sets_today,
        detected_split=detected_split,
        session_adequacy=sess_adequacy,
        weekly_progress=weekly,
    )


def _determine_session_action(
    session_adequacy: SessionAdequacy,
    weekly_progress: WeeklyProgress,
    exercises_today: list[Exercise],
) -> str:
    """
    Determine the recommended session action by combining session
    adequacy and weekly progress.

    Rules:
    - No exercises today + weekly frequency met → rest
    - No exercises today + weekly frequency not met → continue_workout
    - Session adequate → workout_adequate
    - Session not adequate → continue_workout
    - Weekly targets met does NOT automatically mean session is done
    - Weekly targets not met does NOT automatically mean session must continue
    """
    has_exercises = len(exercises_today) > 0

    if not has_exercises:
        if weekly_progress.is_rest_day_eligible:
            return "rest"
        return "continue_workout"

    # If the session is explicitly adequate, trust that evaluation
    if session_adequacy.is_adequate:
        return "workout_adequate"

    # Session is not adequate — keep going
    return "continue_workout"


# ──────────────────────────────────────────────────────────────────────
# NEXT RECOMMENDATIONS
# ──────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────
# TEXT GENERATION
# ──────────────────────────────────────────────────────────────────────

def _generate_adequacy_text(
    today_exercises: list[Exercise],
    session_adequacy: SessionAdequacy,
    weekly_progress: WeeklyProgress,
    session_action: str,
    detected_split: str | None,
    recommended_next: list[str],
    goal: UserGoal | None,
) -> tuple[str, str]:
    """Generate human-readable summary and detail text."""

    goal_type = (goal.goal_type or "fitness").replace("_", " ") if goal else "fitness"

    if len(today_exercises) == 0:
        if session_action == "rest":
            summary = "Rest Day"
            detail = (
                f"You've already trained {weekly_progress.trained_days_this_week} days this week "
                f"(target: {weekly_progress.training_days_target}). Take a rest day to recover."
            )
        else:
            summary = "Ready to Train"
            # Find most undertrained muscles
            undertrained = sorted(
                [mv for mv in weekly_progress.muscle_volumes.values() if mv.status == "undertrained"],
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
        # Use the session adequacy reason which explains WHY it's adequate
        detail = session_adequacy.reason

        # Add weekly context
        undertrained = [mv for mv in weekly_progress.muscle_volumes.values() if mv.status == "undertrained"]
        if undertrained:
            names = sorted([mv.muscle_group.replace("_", "/") for mv in undertrained[:3]])
            detail += f" Next session, prioritize: {', '.join(names)}."

    elif session_action == "continue_workout":
        summary = "Keep Going"
        # Use the session adequacy reason which explains what's needed
        detail = session_adequacy.reason

        # What has been done
        done_str = ", ".join(exercise_names[:3])
        if len(exercise_names) > 3:
            done_str += f" (+{len(exercise_names) - 3} more)"

        if detail:
            detail = f"Logged: {done_str}. {detail}"
        else:
            detail = f"Logged: {done_str}."

    else:  # rest
        summary = "Rest Day"
        detail = "You've met your training frequency for the week. Rest and recover!"

    return summary, detail
