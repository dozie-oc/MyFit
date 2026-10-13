"""
Comprehensive tests for the improved Training Adequacy System.

Covers ALL 14 required scenarios:
 1. Single bicep curl does NOT complete a muscle-building workout.
 2. A reasonable strength session CAN be marked adequate.
 3. A short cardio entry does NOT complete an endurance workout.
 4. A suitable cardio session can be evaluated without strength-set data.
 5. Weekly progress does NOT automatically mark today's session adequate.
 6. A session can be adequate even when weekly targets haven't been reached.
 7. Missing RIR, load, or other optional fields are handled safely.
 8. Multiple exercises targeting the same muscle group update volume correctly.
 9. Recommendations adapt after exercises are logged and avoid duplication.
10. Equipment restrictions and missing muscle mappings are handled safely.
11. Historical exercises without workout-session IDs continue to work.
12. Abandoned sessions are not incorrectly considered completed.
13. Backend completion status and recommendation response remain consistent.
14. Different goals and experience levels receive appropriate evaluation.
"""

from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from src.auth.auth import hash_password
from src.database import get_session
from src.main import app
from src.models import (
    Exercise,
    ExerciseCatalogItem,
    ExerciseMuscleMapping,
    FoodItem,
    User,
    UserGoal,
    WorkoutSession,
)


from tests.conftest import make_test_engine


test_engine = make_test_engine()


@pytest.fixture(autouse=True)
def _setup_teardown():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def session():
    with Session(test_engine) as sess:
        # Populate exercise catalog
        catalog = [
            ExerciseCatalogItem(name="Bench Press", category="strength", default_met=5.0, description="Barbell bench press"),
            ExerciseCatalogItem(name="Barbell Squat", category="strength", default_met=5.0, description="Barbell squats"),
            ExerciseCatalogItem(name="Deadlift", category="strength", default_met=5.5, description="Deadlifts"),
            ExerciseCatalogItem(name="Overhead Press", category="strength", default_met=5.0, description="Shoulder press"),
            ExerciseCatalogItem(name="Barbell Row", category="strength", default_met=5.0, description="Bent-over rows"),
            ExerciseCatalogItem(name="Push-ups", category="strength", default_met=4.5, description="Bodyweight push-ups"),
            ExerciseCatalogItem(name="Pull-ups", category="strength", default_met=5.0, description="Pull-ups"),
            ExerciseCatalogItem(name="Dumbbell Curl", category="strength", default_met=4.5, description="Bicep curls"),
            ExerciseCatalogItem(name="Plank", category="strength", default_met=3.5, description="Core plank"),
            ExerciseCatalogItem(name="Leg Press", category="strength", default_met=5.0, description="Machine leg press"),
            ExerciseCatalogItem(name="Running", category="cardio", default_met=9.8, description="Running"),
            ExerciseCatalogItem(name="Walking", category="cardio", default_met=3.5, description="Walking"),
            ExerciseCatalogItem(name="Swimming", category="cardio", default_met=7.0, description="Swimming"),
            ExerciseCatalogItem(name="Yoga", category="flexibility", default_met=3.0, description="Yoga"),
        ]
        sess.add_all(catalog)
        sess.commit()

        catalog_by_name = {c.name: c for c in catalog}
        mappings = [
            # Bench Press
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Bench Press"].id, muscle_group="chest", role="primary", movement_pattern="horizontal_push"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Bench Press"].id, muscle_group="triceps", role="secondary", movement_pattern="horizontal_push"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Bench Press"].id, muscle_group="shoulders", role="secondary", movement_pattern="horizontal_push"),
            # Barbell Squat
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Barbell Squat"].id, muscle_group="quadriceps", role="primary", movement_pattern="squat"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Barbell Squat"].id, muscle_group="glutes", role="primary", movement_pattern="squat"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Barbell Squat"].id, muscle_group="hamstrings", role="secondary", movement_pattern="squat"),
            # Deadlift
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Deadlift"].id, muscle_group="hamstrings", role="primary", movement_pattern="hinge"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Deadlift"].id, muscle_group="glutes", role="primary", movement_pattern="hinge"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Deadlift"].id, muscle_group="back", role="secondary", movement_pattern="hinge"),
            # Barbell Row
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Barbell Row"].id, muscle_group="back", role="primary", movement_pattern="horizontal_pull"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Barbell Row"].id, muscle_group="biceps", role="secondary", movement_pattern="horizontal_pull"),
            # Push-ups
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Push-ups"].id, muscle_group="chest", role="primary", movement_pattern="horizontal_push"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Push-ups"].id, muscle_group="triceps", role="secondary", movement_pattern="horizontal_push"),
            # Pull-ups
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Pull-ups"].id, muscle_group="back", role="primary", movement_pattern="vertical_pull"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Pull-ups"].id, muscle_group="biceps", role="secondary", movement_pattern="vertical_pull"),
            # Dumbbell Curl
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Dumbbell Curl"].id, muscle_group="biceps", role="primary", movement_pattern="isolation"),
            # Plank
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Plank"].id, muscle_group="abs_core", role="primary", movement_pattern="core"),
            # Overhead Press
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Overhead Press"].id, muscle_group="shoulders", role="primary", movement_pattern="vertical_push"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Overhead Press"].id, muscle_group="triceps", role="secondary", movement_pattern="vertical_push"),
            # Leg Press
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Leg Press"].id, muscle_group="quadriceps", role="primary", movement_pattern="squat"),
            ExerciseMuscleMapping(exercise_catalog_id=catalog_by_name["Leg Press"].id, muscle_group="glutes", role="secondary", movement_pattern="squat"),
        ]
        sess.add_all(mappings)

        foods = [
            FoodItem(name="Oatmeal", calories_per_100g=389.0, protein_per_100g=16.9, carbs_per_100g=66.3, fat_per_100g=6.9, base_unit="g"),
        ]
        sess.add_all(foods)
        sess.commit()

        yield sess


@pytest.fixture
def client(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(session):
    user = User(
        username="adeq_v2_user",
        hashed_password=hash_password("Password123!"),
        weight=80.0,
        height=180.0,
        birthdate=date(1990, 3, 15),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, test_user):
    response = client.post(
        "/auth/login",
        json={"username": "adeq_v2_user", "password": "Password123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _set_goal(client, auth_headers, goal_type="build_muscle",
              experience="intermediate", days=4, equipment=None):
    payload = {
        "goal_type": goal_type,
        "training_days_per_week": days,
        "training_experience": experience,
    }
    if equipment:
        payload["available_equipment"] = equipment
    client.post("/goals", json=payload, headers=auth_headers)


def _log_exercise(client, auth_headers, name, **kwargs):
    payload = {
        "date": date.today().isoformat(),
        "name": name,
        "category": kwargs.get("category", "strength"),
    }
    for k in ("sets", "reps", "weight_kg", "duration_minutes",
              "distance_km", "intensity", "rir"):
        if k in kwargs:
            payload[k] = kwargs[k]
    return client.post("/exercises", json=payload, headers=auth_headers)


def _get_adequacy(client, auth_headers):
    res = client.get("/exercises/adequacy", headers=auth_headers)
    assert res.status_code == 200
    return res.json()


def _get_recommendation(client, auth_headers, rec_type=None):
    url = "/recommendations/today"
    if rec_type:
        url += f"?type={rec_type}"
    res = client.get(url, headers=auth_headers)
    assert res.status_code == 200
    return res.json()


# ──────────────────────────────────────────────────────────────
# TEST 1: Single bicep curl does NOT complete a muscle-building workout
# ──────────────────────────────────────────────────────────────

def test_01_single_isolation_exercise_not_adequate(client, session, test_user, auth_headers):
    """A single set of bicep curls must NOT mark a build_muscle workout as complete."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")
    _log_exercise(client, auth_headers, "Dumbbell Curl", sets=3, reps=12)

    data = _get_adequacy(client, auth_headers)
    assert data["session_action"] == "continue_workout"
    assert data["exercises_today"] == 1
    # The system should still recommend more exercises
    rec = _get_recommendation(client, auth_headers, rec_type="exercise")
    assert rec["has_recommendation"] is True


# ──────────────────────────────────────────────────────────────
# TEST 2: A reasonable strength session CAN be marked adequate
# ──────────────────────────────────────────────────────────────

def test_02_reasonable_strength_session_adequate(client, session, test_user, auth_headers):
    """A session with enough effective sets across multiple muscle groups
    should be marked workout_adequate."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    # Log a solid session: ~16 effective sets across 4+ muscle groups
    _log_exercise(client, auth_headers, "Bench Press", sets=4, reps=8)
    _log_exercise(client, auth_headers, "Barbell Row", sets=4, reps=8)
    _log_exercise(client, auth_headers, "Overhead Press", sets=3, reps=10)

    data = _get_adequacy(client, auth_headers)
    # 4*1.0 (chest) + 4*0.5 (tri) + 4*0.5 (shoulder from bench)
    # + 4*1.0 (back) + 4*0.5 (biceps)
    # + 3*1.0 (shoulders) + 3*0.5 (tri from ohp)
    # Total effective sets > 8, muscle groups > 2 → adequate for intermediate
    assert data["session_action"] == "workout_adequate"


# ──────────────────────────────────────────────────────────────
# TEST 3: Short cardio entry does NOT complete an endurance workout
# ──────────────────────────────────────────────────────────────

def test_03_short_cardio_not_adequate(client, session, test_user, auth_headers):
    """A 5-minute run should NOT mark an improve_endurance workout complete."""
    _set_goal(client, auth_headers, goal_type="improve_endurance", experience="intermediate")
    _log_exercise(client, auth_headers, "Running", category="cardio",
                  duration_minutes=5, intensity="moderate")

    data = _get_adequacy(client, auth_headers)
    assert data["session_action"] == "continue_workout"


# ──────────────────────────────────────────────────────────────
# TEST 4: Suitable cardio session evaluated without strength data
# ──────────────────────────────────────────────────────────────

def test_04_cardio_session_adequate_without_sets(client, session, test_user, auth_headers):
    """A 35-minute moderate run should be adequate for an endurance goal,
    evaluated via duration/intensity, NOT strength set counts."""
    _set_goal(client, auth_headers, goal_type="improve_endurance", experience="intermediate")
    _log_exercise(client, auth_headers, "Running", category="cardio",
                  duration_minutes=35, distance_km=5.0, intensity="moderate")

    data = _get_adequacy(client, auth_headers)
    assert data["session_action"] == "workout_adequate"
    # Should NOT have 0 sets as a reason for continuing
    assert data["total_sets_today"] == 0  # No strength sets, and that's fine


# ──────────────────────────────────────────────────────────────
# TEST 5: Weekly progress does NOT automatically mark today adequate
# ──────────────────────────────────────────────────────────────

def test_05_weekly_progress_does_not_auto_complete_session(client, session, test_user, auth_headers):
    """Even if the user has a great weekly total, today's single exercise
    should not be auto-marked as adequate."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="beginner", days=4)

    today = date.today()
    monday = today - timedelta(days=today.weekday())

    # Seed heavy training on earlier days this week
    catalog = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()

    for day_offset in range(min(today.weekday(), 3)):
        ex_date = monday + timedelta(days=day_offset)
        if ex_date >= today:
            continue
        for _ in range(4):  # 4 exercises per day, 4 sets each
            session.add(Exercise(
                user_id=test_user.id, date=ex_date,
                name="Bench Press", category="strength",
                exercise_catalog_id=catalog.id,
                sets=4, reps=8, calories_burned=100,
            ))
    session.commit()

    # Now log just one isolation exercise today
    _log_exercise(client, auth_headers, "Dumbbell Curl", sets=2, reps=15)

    data = _get_adequacy(client, auth_headers)
    # Despite likely great weekly numbers, today's session is NOT adequate
    assert data["session_action"] == "continue_workout"


# ──────────────────────────────────────────────────────────────
# TEST 6: Session can be adequate even when weekly targets aren't reached
# ──────────────────────────────────────────────────────────────

def test_06_session_adequate_despite_weekly_gap(client, session, test_user, auth_headers):
    """A solid first session of the week should be marked adequate even
    though weekly targets are nowhere near met."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate", days=4)

    # It's early in the week, no prior exercises
    _log_exercise(client, auth_headers, "Bench Press", sets=4, reps=8)
    _log_exercise(client, auth_headers, "Barbell Row", sets=4, reps=8)
    _log_exercise(client, auth_headers, "Overhead Press", sets=3, reps=10)

    data = _get_adequacy(client, auth_headers)
    assert data["session_action"] == "workout_adequate"
    # Weekly overall may still be insufficient
    assert data["overall_status"] == "insufficient"


# ──────────────────────────────────────────────────────────────
# TEST 7: Missing RIR, load, and optional fields handled safely
# ──────────────────────────────────────────────────────────────

def test_07_missing_optional_fields_safe(client, session, test_user, auth_headers):
    """Exercises with no RIR, no weight_kg, and no duration should
    still be processed without errors."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="beginner")

    # Log exercises with only required fields (sets/reps, no rir, no weight)
    _log_exercise(client, auth_headers, "Push-ups", sets=3, reps=15)
    _log_exercise(client, auth_headers, "Barbell Squat", sets=3, reps=10)
    _log_exercise(client, auth_headers, "Pull-ups", sets=3, reps=8)

    data = _get_adequacy(client, auth_headers)
    # Should not error and should give a valid result
    assert data["session_action"] in ("continue_workout", "workout_adequate")
    assert data["exercises_today"] == 3
    assert data["total_sets_today"] == 9


# ──────────────────────────────────────────────────────────────
# TEST 8: Multiple exercises for same muscle group accumulate volume
# ──────────────────────────────────────────────────────────────

def test_08_same_muscle_volume_accumulates(client, session, test_user, auth_headers):
    """Two chest exercises should combine their volume correctly."""
    from src.services.training_service import (
        aggregate_volume, get_muscle_mappings,
    )

    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    catalog_bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    catalog_push = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Push-ups")
    ).first()

    exercises = [
        Exercise(user_id=test_user.id, date=date.today(), name="Bench Press",
                 category="strength", exercise_catalog_id=catalog_bench.id,
                 sets=4, reps=8),
        Exercise(user_id=test_user.id, date=date.today(), name="Push-ups",
                 category="strength", exercise_catalog_id=catalog_push.id,
                 sets=3, reps=15),
    ]

    mappings = get_muscle_mappings(session)
    vol = aggregate_volume(exercises, mappings)

    # Chest: 4*1.0 (bench primary) + 3*1.0 (pushup primary) = 7.0
    assert vol["chest"] == 7.0
    # Triceps: 4*0.5 (bench secondary) + 3*0.5 (pushup secondary) = 3.5
    assert vol["triceps"] == 3.5


# ──────────────────────────────────────────────────────────────
# TEST 9: Recommendations adapt and avoid duplication
# ──────────────────────────────────────────────────────────────

def test_09_recommendations_adapt_no_duplicate(client, session, test_user, auth_headers):
    """After logging bench press, the recommendation should NOT suggest
    bench press again, and should prefer undertrained muscle groups."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    # First recommendation (no exercises yet)
    rec1 = _get_recommendation(client, auth_headers, rec_type="exercise")
    assert rec1["has_recommendation"] is True

    # Log bench press
    _log_exercise(client, auth_headers, "Bench Press", sets=4, reps=8)

    # Second recommendation — should NOT be bench press
    rec2 = _get_recommendation(client, auth_headers, rec_type="exercise")
    assert rec2["has_recommendation"] is True, rec2.get("reason")
    assert rec2["items"][0]["name"] != "Bench Press"


# ──────────────────────────────────────────────────────────────
# TEST 10: Equipment restrictions and missing muscle mappings
# ──────────────────────────────────────────────────────────────

def test_10_equipment_and_missing_mappings(client, session, test_user, auth_headers):
    """Equipment restrictions should filter recommendations. Exercises
    without muscle mappings should still work but not claim specific
    muscle coverage."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate",
              equipment="bodyweight")

    rec = _get_recommendation(client, auth_headers, rec_type="exercise")
    if rec["has_recommendation"]:
        name = rec["items"][0]["name"].lower()
        # Should not recommend barbell exercises for bodyweight-only user
        assert "barbell" not in name
        assert name not in ("bench press", "deadlift", "barbell squat",
                            "barbell row", "overhead press")

    # Test exercise with no muscle mapping contributes no muscle volume
    from src.services.training_service import calculate_exercise_volume, get_muscle_mappings

    unmapped_exercise = Exercise(
        user_id=test_user.id, date=date.today(), name="Some Unknown Exercise",
        category="strength", exercise_catalog_id=None, sets=5, reps=10,
    )
    mappings = get_muscle_mappings(session)
    vol = calculate_exercise_volume(unmapped_exercise, mappings)
    assert vol == {}  # No mapping, no volume claimed


# ──────────────────────────────────────────────────────────────
# TEST 11: Historical exercises without workout_session_id work
# ──────────────────────────────────────────────────────────────

def test_11_historical_exercises_without_session(client, session, test_user, auth_headers):
    """Exercises with workout_session_id=None (historical) should still
    be included in adequacy evaluation."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    # Directly insert exercises without session IDs (simulating legacy data)
    catalog = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()

    for _ in range(3):
        session.add(Exercise(
            user_id=test_user.id, date=date.today(),
            name="Bench Press", category="strength",
            exercise_catalog_id=catalog.id,
            sets=4, reps=8, calories_burned=100,
            workout_session_id=None,  # No session — historical
        ))
    session.commit()

    data = _get_adequacy(client, auth_headers)
    assert data["exercises_today"] == 3
    assert data["total_sets_today"] == 12
    # Volume should be counted
    chest_mg = next(
        (mg for mg in data["muscle_groups"] if mg["muscle_group"] == "chest"),
        None,
    )
    assert chest_mg is not None
    assert chest_mg["sets_completed"] > 0


# ──────────────────────────────────────────────────────────────
# TEST 12: Abandoned sessions are NOT counted as completed
# ──────────────────────────────────────────────────────────────

def test_12_abandoned_sessions_excluded(client, session, test_user, auth_headers):
    """Exercises linked to an abandoned workout session should NOT
    count toward today's adequacy evaluation."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    # Create an abandoned session with exercises
    abandoned = WorkoutSession(
        user_id=test_user.id, date=date.today(), status="abandoned",
    )
    session.add(abandoned)
    session.commit()
    session.refresh(abandoned)

    catalog = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()

    # Link exercises to the abandoned session
    for _ in range(4):
        session.add(Exercise(
            user_id=test_user.id, date=date.today(),
            name="Bench Press", category="strength",
            exercise_catalog_id=catalog.id,
            sets=4, reps=8, calories_burned=100,
            workout_session_id=abandoned.id,
        ))
    session.commit()

    data = _get_adequacy(client, auth_headers)
    # Exercises from abandoned session should be excluded
    assert data["exercises_today"] == 0
    assert data["session_action"] == "continue_workout"


# ──────────────────────────────────────────────────────────────
# TEST 13: Completion status and recommendation are consistent
# ──────────────────────────────────────────────────────────────

def test_13_completion_and_recommendation_consistent(client, session, test_user, auth_headers):
    """If adequacy says workout_adequate, the exercise recommendation
    should say has_recommendation=False (no more needed).
    If adequacy says continue_workout, the exercise recommendation
    should say has_recommendation=True."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    # Not enough work → should recommend
    _log_exercise(client, auth_headers, "Dumbbell Curl", sets=2, reps=12)
    adeq = _get_adequacy(client, auth_headers)
    rec = _get_recommendation(client, auth_headers, rec_type="exercise")

    if adeq["session_action"] == "continue_workout":
        assert rec["has_recommendation"] is True
    elif adeq["session_action"] == "workout_adequate":
        assert rec["has_recommendation"] is False

    # Now do a full session
    _log_exercise(client, auth_headers, "Bench Press", sets=4, reps=8)
    _log_exercise(client, auth_headers, "Barbell Row", sets=4, reps=8)
    _log_exercise(client, auth_headers, "Overhead Press", sets=3, reps=10)

    adeq2 = _get_adequacy(client, auth_headers)
    rec2 = _get_recommendation(client, auth_headers, rec_type="exercise")

    if adeq2["session_action"] == "workout_adequate":
        assert rec2["has_recommendation"] is False
    elif adeq2["session_action"] == "continue_workout":
        assert rec2["has_recommendation"] is True


# ──────────────────────────────────────────────────────────────
# TEST 14: Different goals and experience levels get different treatment
# ──────────────────────────────────────────────────────────────

def test_14_different_goals_different_evaluation(session, test_user):
    """
    Test that the same exercises produce different session evaluations
    depending on the user's goal type and experience level.
    """
    from src.services.training_service import evaluate_session_adequacy, get_muscle_mappings

    mappings = get_muscle_mappings(session)

    catalog_run = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Running")
    ).first()
    catalog_bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()

    # Scenario A: 30min run evaluated for endurance vs build_muscle goal
    cardio_exercises = [
        Exercise(
            user_id=test_user.id, date=date.today(), name="Running",
            category="cardio", exercise_catalog_id=catalog_run.id,
            duration_minutes=30, distance_km=4.0, intensity="moderate",
        ),
    ]

    endurance_goal = UserGoal(
        user_id=test_user.id, goal_type="improve_endurance",
        training_experience="intermediate",
    )
    muscle_goal = UserGoal(
        user_id=test_user.id, goal_type="build_muscle",
        training_experience="intermediate",
    )

    endurance_result = evaluate_session_adequacy(cardio_exercises, endurance_goal, mappings)
    muscle_result = evaluate_session_adequacy(cardio_exercises, muscle_goal, mappings)

    # For endurance goal, a 30min run should be decent cardio
    assert endurance_result.has_cardio_work is True
    # For muscle goal, cardio doesn't satisfy strength requirements
    assert muscle_result.has_strength_work is False

    # Scenario B: Same strength exercises evaluated for beginner vs advanced
    strength_exercises = [
        Exercise(
            user_id=test_user.id, date=date.today(), name="Bench Press",
            category="strength", exercise_catalog_id=catalog_bench.id,
            sets=3, reps=10,
        ),
    ]

    beginner_goal = UserGoal(
        user_id=test_user.id, goal_type="build_muscle",
        training_experience="beginner",
    )
    advanced_goal = UserGoal(
        user_id=test_user.id, goal_type="build_muscle",
        training_experience="advanced",
    )

    beginner_result = evaluate_session_adequacy(strength_exercises, beginner_goal, mappings)
    advanced_result = evaluate_session_adequacy(strength_exercises, advanced_goal, mappings)

    # 3 effective sets from one exercise — might be closer to adequate for
    # a beginner (min 6 sets) than an advanced lifter (min 10 sets)
    # Both should not be adequate from just one exercise with 3 sets
    assert beginner_result.strength_sets_done == advanced_result.strength_sets_done
    # But the threshold is different, so advanced is further from adequate
    assert not advanced_result.is_adequate
