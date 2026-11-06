"""
Comprehensive tests for the improved Training Adequacy System.

Covers ALL 14 required scenarios:
 1. Single bicep curl does NOT complete a muscle-building workout.
 2. A reasonable strength session CAN be marked adequate.
 3. A short cardio entry does NOT complete an endurance workout.
 4. A suitable cardio session can be evaluated without strength-set data.
 5. Weekly progress does NOT automatically mark today's session adequate.
 6. A session can be adequate even when weekly targets haven't been reached.
 7. Missing effort_rating, load, or other optional fields are handled safely.
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
            ExerciseCatalogItem(name="Bench Press", category="strength", default_met=5.0, equipment="barbell", description="Barbell bench press"),
            ExerciseCatalogItem(name="Barbell Squat", category="strength", default_met=5.0, equipment="barbell", description="Barbell squats"),
            ExerciseCatalogItem(name="Deadlift", category="strength", default_met=5.5, equipment="barbell", level="advanced", description="Deadlifts"),
            ExerciseCatalogItem(name="Overhead Press", category="strength", default_met=5.0, equipment="barbell", description="Shoulder press"),
            ExerciseCatalogItem(name="Barbell Row", category="strength", default_met=5.0, equipment="barbell", description="Bent-over rows"),
            ExerciseCatalogItem(name="Push-ups", category="strength", default_met=4.5, equipment="bodyweight", level="beginner", description="Bodyweight push-ups"),
            ExerciseCatalogItem(name="Pull-ups", category="strength", default_met=5.0, equipment="bodyweight", description="Pull-ups"),
            ExerciseCatalogItem(name="Dumbbell Curl", category="strength", default_met=4.5, equipment="dumbbell", level="beginner", description="Bicep curls"),
            ExerciseCatalogItem(name="Plank", category="strength", default_met=3.5, equipment="bodyweight", level="beginner", description="Core plank"),
            ExerciseCatalogItem(name="Leg Press", category="strength", default_met=5.0, equipment="machines", level="beginner", description="Machine leg press"),
            ExerciseCatalogItem(name="Running", category="cardio", default_met=9.8, equipment="bodyweight", level="beginner", description="Running"),
            ExerciseCatalogItem(name="Walking", category="cardio", default_met=3.5, equipment="bodyweight", level="beginner", description="Walking"),
            ExerciseCatalogItem(name="Swimming", category="cardio", default_met=7.0, equipment="bodyweight", level="beginner", description="Swimming"),
            ExerciseCatalogItem(name="Yoga", category="flexibility", default_met=3.0, equipment="bodyweight", level="beginner", description="Yoga"),
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
              "distance_km", "intensity", "effort_rating"):
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
# TEST 7: Missing effort_rating, load, and optional fields handled safely
# ──────────────────────────────────────────────────────────────

def test_07_missing_optional_fields_safe(client, session, test_user, auth_headers):
    """Exercises with no effort_rating, no weight_kg, and no duration should
    still be processed without errors."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="beginner")

    # Log exercises with only required fields (sets/reps, no effort_rating, no weight)
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


# ──────────────────────────────────────────────────────────────
# TEST 15: New exercises are associated with the intended workout session
# ──────────────────────────────────────────────────────────────

def test_15_new_exercises_associated_with_workout_session(client, session, test_user, auth_headers):
    """Logging exercises associates them with the active WorkoutSession,
    or with an explicitly specified workout_session_id."""
    ex1 = _log_exercise(client, auth_headers, "Bench Press", sets=3, reps=8).json()
    ex2 = _log_exercise(client, auth_headers, "Barbell Row", sets=3, reps=8).json()

    assert ex1["workout_session_id"] is not None
    assert ex2["workout_session_id"] == ex1["workout_session_id"]

    # Complete the first session and log a new exercise -> gets a new session
    session_1_id = ex1["workout_session_id"]
    resp = client.patch(
        f"/exercises/sessions/{session_1_id}",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    ex3 = _log_exercise(client, auth_headers, "Overhead Press", sets=3, reps=10).json()
    assert ex3["workout_session_id"] is not None
    assert ex3["workout_session_id"] != session_1_id


# ──────────────────────────────────────────────────────────────
# TEST 16: Two sessions on the same date remain separate
# ──────────────────────────────────────────────────────────────

def test_16_two_sessions_on_same_date_remain_separate(client, session, test_user, auth_headers):
    """Two workout sessions on the same date must not be combined during
    session retrieval, adequacy evaluation, or recommendation checks."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    # Morning session: Bench Press + Barbell Row + Overhead Press (completed)
    m1 = _log_exercise(client, auth_headers, "Bench Press", sets=4, reps=8).json()
    m2 = _log_exercise(client, auth_headers, "Barbell Row", sets=4, reps=8).json()
    m3 = _log_exercise(client, auth_headers, "Overhead Press", sets=3, reps=10).json()
    morning_session_id = m1["workout_session_id"]
    assert m2["workout_session_id"] == morning_session_id
    assert m3["workout_session_id"] == morning_session_id

    # Start an afternoon session on the same date (automatically completes morning session)
    start_resp = client.post("/exercises/sessions", json={}, headers=auth_headers)
    assert start_resp.status_code == 201
    afternoon_session_id = start_resp.json()["id"]
    assert afternoon_session_id != morning_session_id

    # Log 1 exercise in the afternoon session
    a1 = _log_exercise(client, auth_headers, "Barbell Squat", sets=3, reps=8).json()
    assert a1["workout_session_id"] == afternoon_session_id

    # Current session adequacy must ONLY reflect the afternoon session (1 exercise, 3 sets)
    adeq_current = _get_adequacy(client, auth_headers)
    assert adeq_current["exercises_today"] == 1
    assert adeq_current["total_sets_today"] == 3

    # Morning session adequacy when queried explicitly reflects ONLY the morning session (3 exercises, 11 sets)
    adeq_morning_resp = client.get(
        f"/exercises/adequacy?workout_session_id={morning_session_id}",
        headers=auth_headers,
    )
    assert adeq_morning_resp.status_code == 200
    adeq_morning = adeq_morning_resp.json()
    assert adeq_morning["exercises_today"] == 3
    assert adeq_morning["total_sets_today"] == 11

    # Session retrieval returns ONLY each session's own exercises
    morning_ex_resp = client.get(
        f"/exercises?workout_session_id={morning_session_id}",
        headers=auth_headers,
    )
    assert morning_ex_resp.status_code == 200
    morning_names = [e["name"] for e in morning_ex_resp.json()]
    assert morning_names == ["Bench Press", "Barbell Row", "Overhead Press"]

    afternoon_ex_resp = client.get(
        f"/exercises/sessions/{afternoon_session_id}/exercises",
        headers=auth_headers,
    )
    assert afternoon_ex_resp.status_code == 200
    afternoon_names = [e["name"] for e in afternoon_ex_resp.json()]
    assert afternoon_names == ["Barbell Squat"]


# ──────────────────────────────────────────────────────────────
# TEST 17: Unlinked exercises do not leak into active sessions
#          while workout history preserves all records
# ──────────────────────────────────────────────────────────────

def test_17_unlinked_exercises_do_not_leak_into_session_and_history_preserved(
    client, session, test_user, auth_headers,
):
    """Unlinked legacy exercises on the same date must not be combined into
    a WorkoutSession's exercises, while full workout history (`GET /exercises`
    and `GET /exercises/last`) preserves both unlinked and session-linked records."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    catalog_bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()

    # Insert an unlinked historical exercise on today
    unlinked = Exercise(
        user_id=test_user.id,
        date=date.today(),
        name="Bench Press",
        category="strength",
        exercise_catalog_id=catalog_bench.id,
        sets=4,
        reps=8,
        weight_kg=80.0,
        calories_burned=100.0,
        workout_session_id=None,
    )
    session.add(unlinked)
    session.commit()
    session.refresh(unlinked)

    # Now log a new exercise in a tracked session on today
    logged = _log_exercise(
        client, auth_headers, "Dumbbell Curl", sets=3, reps=12, weight_kg=15.0,
    ).json()
    ws_id = logged["workout_session_id"]
    assert ws_id is not None

    # Session retrieval must return ONLY Dumbbell Curl (not the unlinked Bench Press)
    sess_ex_resp = client.get(
        f"/exercises?workout_session_id={ws_id}",
        headers=auth_headers,
    )
    assert sess_ex_resp.status_code == 200
    sess_ex = sess_ex_resp.json()
    assert len(sess_ex) == 1
    assert sess_ex[0]["name"] == "Dumbbell Curl"

    # Current session adequacy must count ONLY the active session (1 exercise, 3 sets)
    adeq = _get_adequacy(client, auth_headers)
    assert adeq["exercises_today"] == 1
    assert adeq["total_sets_today"] == 3

    # Full workout history (`GET /exercises` without workout_session_id) preserves both!
    all_ex_resp = client.get("/exercises", headers=auth_headers)
    assert all_ex_resp.status_code == 200
    all_names = {e["name"] for e in all_ex_resp.json()}
    assert all_names == {"Bench Press", "Dumbbell Curl"}

    # Personal record / last history (`GET /exercises/last`) still finds the unlinked Bench Press
    hist_resp = client.get(
        f"/exercises/last?exercise_catalog_id={catalog_bench.id}",
        headers=auth_headers,
    )
    assert hist_resp.status_code == 200
    assert hist_resp.json()["times_logged"] == 1
    assert hist_resp.json()["best_weight_kg"] == 80.0


# ──────────────────────────────────────────────────────────────
# TEST 18: Direct service & router verification of session separation
# ──────────────────────────────────────────────────────────────

def test_18_workout_session_service_and_router_direct(session, test_user):
    """Direct verification of workout session association, same-day session
    separation, explicit session retrieval, and unlinked record safety."""
    from src.routers.exercises import (
        create_exercise,
        create_workout_session,
        get_exercises,
        get_training_adequacy,
        get_workout_session_exercises,
        update_workout_session,
    )
    from src.schemas import (
        ExerciseLogCreate,
        WorkoutSessionCreate,
        WorkoutSessionUpdate,
    )
    from src.services.training_service import get_current_session_exercises

    today = date.today()
    goal = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
    )
    session.add(goal)
    session.commit()

    # 1. Unlinked legacy exercise on yesterday and today
    catalog_bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    unlinked_today = Exercise(
        user_id=test_user.id,
        date=today,
        name="Bench Press",
        category="strength",
        exercise_catalog_id=catalog_bench.id,
        sets=4,
        reps=8,
        weight_kg=75.0,
        calories_burned=90.0,
        workout_session_id=None,
    )
    session.add(unlinked_today)
    session.commit()

    # Before any WorkoutSession exists on today, unlinked exercise is returned safely
    initial_current = get_current_session_exercises(session, test_user.id, today)
    assert len(initial_current) == 1
    assert initial_current[0].name == "Bench Press"

    # 2. Log two exercises in Session 1 -> automatically creates and shares Session 1
    ex1 = create_exercise(
        ExerciseLogCreate(date=today, name="Barbell Row", category="strength", sets=4, reps=8),
        session=session,
        current_user=test_user,
    )
    ex2 = create_exercise(
        ExerciseLogCreate(date=today, name="Overhead Press", category="strength", sets=3, reps=10),
        session=session,
        current_user=test_user,
    )
    assert ex1.workout_session_id is not None
    assert ex2.workout_session_id == ex1.workout_session_id
    session_1_id = ex1.workout_session_id

    # Session 1 retrieval returns ONLY its 2 exercises (not the unlinked Bench Press)
    s1_exercises = get_workout_session_exercises(
        session_id=session_1_id, session=session, current_user=test_user
    )
    assert [e.name for e in s1_exercises] == ["Barbell Row", "Overhead Press"]

    # 3. Start Session 2 on the same date -> completes Session 1 and starts Session 2
    s2 = create_workout_session(
        session=session,
        current_user=test_user,
        session_data=WorkoutSessionCreate(date=today, notes="Evening legs"),
    )
    assert s2.id != session_1_id
    assert s2.status == "active"

    # Log 1 exercise in Session 2
    ex3 = create_exercise(
        ExerciseLogCreate(date=today, name="Barbell Squat", category="strength", sets=5, reps=5),
        session=session,
        current_user=test_user,
    )
    assert ex3.workout_session_id == s2.id

    # Current session exercises must ONLY be Session 2's Barbell Squat
    current_after_s2 = get_current_session_exercises(session, test_user.id, today)
    assert [e.name for e in current_after_s2] == ["Barbell Squat"]

    # Adequacy for current session vs explicit Session 1
    adeq_s2 = get_training_adequacy(session=session, current_user=test_user)
    assert adeq_s2.exercises_today == 1
    assert adeq_s2.total_sets_today == 5

    adeq_s1 = get_training_adequacy(
        session=session, current_user=test_user, workout_session_id=session_1_id
    )
    assert adeq_s1.exercises_today == 2
    assert adeq_s1.total_sets_today == 7

    # Complete Session 2; current session on today should still resolve to latest completed (Session 2)
    update_workout_session(
        session_id=s2.id,
        session_data=WorkoutSessionUpdate(status="completed"),
        session=session,
        current_user=test_user,
    )
    current_completed = get_current_session_exercises(session, test_user.id, today)
    assert [e.name for e in current_completed] == ["Barbell Squat"]

    # Full history (`get_exercises` without workout_session_id) preserves all 4 exercises
    all_history = get_exercises(session=session, current_user=test_user, exercise_date=today)
    assert len(all_history) == 4


# ──────────────────────────────────────────────────────────────
# TEST 19: Cardio duration present calculates without distance fabrication
# ──────────────────────────────────────────────────────────────

def test_19_cardio_duration_present_calculates_without_distance_fabrication(
    client, session, test_user, auth_headers,
):
    """When cardio duration is present, effective minutes are derived from
    duration and intensity. Distance is recorded but does not fabricate
    additional effective minutes."""
    _set_goal(client, auth_headers, goal_type="improve_endurance", experience="intermediate")

    _log_exercise(
        client,
        auth_headers,
        "Running",
        category="cardio",
        duration_minutes=35,
        distance_km=5.0,
        intensity="moderate",
    )

    data = _get_adequacy(client, auth_headers)
    assert data["session_action"] == "workout_adequate"

    cardio = data.get("cardio_status")
    assert cardio is not None
    assert cardio["total_duration_minutes"] == 35.0
    # Effective minutes must be exactly 35.0 (35 * 1.0) — distance of 5.0km must NOT add bonus minutes
    assert cardio["effective_duration_minutes"] == 35.0
    assert cardio["total_distance_km"] == 5.0
    assert cardio["has_missing_duration"] is False
    assert cardio["duration_status"] == "complete"
    assert cardio["has_meaningful_cardio"] is True


# ──────────────────────────────────────────────────────────────
# TEST 20: Cardio duration missing is represented as unknown or incomplete
# ──────────────────────────────────────────────────────────────

def test_20_cardio_duration_missing_represented_as_unknown_or_incomplete(
    client, session, test_user, auth_headers,
):
    """When cardio exercise has missing duration (None), no default duration
    is assumed, distance does not fabricate effective minutes, and the status
    is represented as unknown/incomplete with low confidence."""
    _set_goal(client, auth_headers, goal_type="improve_endurance", experience="intermediate")

    # Log cardio with distance but NO duration
    _log_exercise(
        client,
        auth_headers,
        "Running",
        category="cardio",
        duration_minutes=None,
        distance_km=10.0,
        intensity="moderate",
    )

    data = _get_adequacy(client, auth_headers)
    # Must NOT be marked adequate despite logging 10km!
    assert data["session_action"] == "continue_workout"

    cardio = data.get("cardio_status")
    assert cardio is not None
    # No assumed 5 minutes!
    assert cardio["total_duration_minutes"] == 0.0
    # Distance does NOT fabricate effective minutes!
    assert cardio["effective_duration_minutes"] == 0.0
    # Distance is recorded faithfully
    assert cardio["total_distance_km"] == 10.0
    # Represented as unknown / missing duration
    assert cardio["has_missing_duration"] is True
    assert cardio["duration_status"] == "unknown"
    assert cardio["has_meaningful_cardio"] is False

    # Explanation indicates unknown duration
    assert "unknown" in data["detail"].lower() or "duration" in data["detail"].lower()


# ──────────────────────────────────────────────────────────────
# TEST 21: Cardio duration zero does not fabricate effective minutes
# ──────────────────────────────────────────────────────────────

def test_21_cardio_duration_zero_does_not_fabricate_minutes(
    client, session, test_user, auth_headers,
):
    """When duration is explicitly zero, effective minutes remain zero,
    distance does not fabricate minutes, and the session is not adequate."""
    _set_goal(client, auth_headers, goal_type="improve_endurance", experience="intermediate")

    from src.routers.exercises import create_exercise
    from src.schemas import ExerciseLogCreate

    # Log with duration_minutes=0
    create_exercise(
        ExerciseLogCreate(
            date=date.today(),
            name="Cycling",
            category="cardio",
            duration_minutes=None,
            distance_km=15.0,
            intensity="moderate",
        ),
        session=session,
        current_user=test_user,
    )
    # Also test evaluate_cardio_session directly with duration_minutes=0
    from src.services.training_service import evaluate_cardio_session

    zero_exercise = Exercise(
        user_id=test_user.id,
        date=date.today(),
        name="Running",
        category="cardio",
        duration_minutes=0,
        distance_km=8.0,
        intensity="moderate",
    )
    status = evaluate_cardio_session([zero_exercise], experience="intermediate")
    assert status.total_duration_minutes == 0.0
    assert status.effective_duration_minutes == 0.0
    assert status.total_distance_km == 8.0
    assert status.has_meaningful_cardio is False


# ──────────────────────────────────────────────────────────────
# TEST 22: Mixed cardio session represents partial data as incomplete
# ──────────────────────────────────────────────────────────────

def test_22_mixed_cardio_session_represents_incomplete_duration(
    session, test_user,
):
    """When some cardio exercises have duration and others are missing duration,
    the session status is represented as 'incomplete' and only known durations count."""
    from src.services.training_service import evaluate_cardio_session

    ex_with_duration = Exercise(
        user_id=test_user.id,
        date=date.today(),
        name="Running",
        category="cardio",
        duration_minutes=25,
        distance_km=4.0,
        intensity="moderate",
    )
    ex_missing_duration = Exercise(
        user_id=test_user.id,
        date=date.today(),
        name="Walking",
        category="cardio",
        duration_minutes=None,
        distance_km=2.0,
        intensity="low",
    )

    status = evaluate_cardio_session(
        [ex_with_duration, ex_missing_duration],
        experience="intermediate",
    )
    assert status.total_duration_minutes == 25.0
    assert status.effective_duration_minutes == 25.0
    assert status.total_distance_km == 6.0
    assert status.has_missing_duration is True
    assert status.missing_duration_count == 1
    assert status.duration_status == "incomplete"


# ──────────────────────────────────────────────────────────────
# TEST 23: Small number of exercises or single-muscle work stays incomplete
# ──────────────────────────────────────────────────────────────

def test_23_small_exercise_count_or_single_primary_muscle_not_adequate(
    client, session, test_user, auth_headers,
):
    """Completing only 2 exercises (even if secondary muscle credits inflate
    total effective sets) or only targeting 1 primary muscle group must NOT
    mark the workout adequate."""
    _set_goal(client, auth_headers, goal_type="build_muscle", experience="intermediate")

    # 2 compound chest exercises (4 raw sets total, 8.0 summed muscle-credit sets)
    _log_exercise(client, auth_headers, "Bench Press", sets=2, reps=8)
    _log_exercise(client, auth_headers, "Push-ups", sets=2, reps=12)

    data = _get_adequacy(client, auth_headers)
    assert data["session_action"] == "continue_workout"
    assert data["summary"] == "Keep Going"

    # Even with more sets across only 2 exercises targeting 1 primary muscle (chest),
    # still incomplete because exercise variety (<3) and primary muscle structure (<2) are lacking
    _log_exercise(client, auth_headers, "Bench Press", sets=3, reps=8)
    _log_exercise(client, auth_headers, "Push-ups", sets=3, reps=12)
    data2 = _get_adequacy(client, auth_headers)
    assert data2["session_action"] == "continue_workout"

    # Once a 3rd distinct exercise targeting a 2nd primary muscle group (back) is added -> adequate!
    _log_exercise(client, auth_headers, "Barbell Row", sets=4, reps=8)
    data3 = _get_adequacy(client, auth_headers)
    assert data3["session_action"] == "workout_adequate"
    assert data3["summary"] == "Workout Adequate"


# ──────────────────────────────────────────────────────────────
# TEST 24: Mixed goal requires meaningful structure (no trivial completion)
# ──────────────────────────────────────────────────────────────

def test_24_mixed_goal_incomplete_vs_adequate(
    client, session, test_user, auth_headers,
):
    """For mixed goals (improve_fitness), a small amount of strength + short
    cardio stays incomplete, whereas a meaningful hybrid or structured session
    is marked workout_adequate."""
    _set_goal(client, auth_headers, goal_type="improve_fitness", experience="intermediate")

    # Small activity: 1 strength exercise (2 sets) + 10 min cardio (< 20 min minimum)
    _log_exercise(client, auth_headers, "Push-ups", sets=2, reps=10)
    _log_exercise(
        client, auth_headers, "Walking", category="cardio", duration_minutes=10,
    )
    adeq_incomplete = _get_adequacy(client, auth_headers)
    assert adeq_incomplete["session_action"] == "continue_workout"

    # Add a 2nd strength exercise (bringing working sets >= 5 across 2 exercises)
    # and a meaningful 20-min run -> hybrid mixed session is now adequate!
    _log_exercise(client, auth_headers, "Barbell Row", sets=3, reps=10)
    _log_exercise(
        client, auth_headers, "Running", category="cardio", duration_minutes=20,
    )
    adeq_complete = _get_adequacy(client, auth_headers)
    assert adeq_complete["session_action"] == "workout_adequate"


# ──────────────────────────────────────────────────────────────
# TEST 25: Trivial activity on prior days does NOT trigger a rest day
# ──────────────────────────────────────────────────────────────

def test_25_trivial_prior_days_do_not_trigger_rest_day(
    session, test_user,
):
    """Logging 1 trivial set on prior days of the week must not count as
    completed training days or trigger rest-day status."""
    from src.services.training_service import evaluate_training_adequacy

    # Use a fixed Thursday so Monday, Tuesday, Wednesday are in the same week
    thursday = date(2026, 11, 5)
    monday = thursday - timedelta(days=3)

    goal = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        training_days_per_week=3,
    )
    session.add(goal)

    catalog_curl = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Dumbbell Curl")
    ).first()

    # Log just 1 set of curls on Mon, Tue, Wed
    for offset in range(3):
        session.add(
            Exercise(
                user_id=test_user.id,
                date=monday + timedelta(days=offset),
                name="Dumbbell Curl",
                category="strength",
                exercise_catalog_id=catalog_curl.id,
                sets=1,
                reps=10,
                calories_burned=15.0,
            )
        )
    session.commit()

    adequacy = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal, today=thursday,
    )
    assert adequacy.weekly_progress.trained_days_this_week == 0
    assert adequacy.weekly_progress.is_rest_day_eligible is False
    assert adequacy.session_action == "continue_workout"
    assert adequacy.summary == "Ready to Train"


# ──────────────────────────────────────────────────────────────
# TEST 26: Rest-day behavior is distinct from workout completion
# ──────────────────────────────────────────────────────────────

def test_26_rest_day_distinct_from_workout_completion(
    session, test_user,
):
    """When meaningful workouts on prior days meet training_days_per_week:
    - With 0 exercises today: session_action is 'rest' (Summary: 'Rest Day'),
      and recommendations describe a scheduled rest day rather than claiming
      a workout was completed today.
    - Once an exercise is logged today: session_action transitions to
      'continue_workout' (and then 'workout_adequate' when completed),
      never confusing an active workout with a rest day."""
    from src.services.recommendation_service import get_recommendation
    from src.services.training_service import evaluate_training_adequacy

    thursday = date(2026, 11, 5)
    monday = thursday - timedelta(days=3)

    goal = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        training_days_per_week=3,
    )
    session.add(goal)

    bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    row = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Barbell Row")
    ).first()
    ohp = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Overhead Press")
    ).first()

    # Seed 3 meaningful workouts on Monday, Tuesday, Wednesday
    for offset in range(3):
        d = monday + timedelta(days=offset)
        session.add(
            Exercise(
                user_id=test_user.id, date=d, name="Bench Press", category="strength",
                exercise_catalog_id=bench.id, sets=4, reps=8, calories_burned=80.0,
            )
        )
        session.add(
            Exercise(
                user_id=test_user.id, date=d, name="Barbell Row", category="strength",
                exercise_catalog_id=row.id, sets=4, reps=8, calories_burned=80.0,
            )
        )
        session.add(
            Exercise(
                user_id=test_user.id, date=d, name="Overhead Press", category="strength",
                exercise_catalog_id=ohp.id, sets=3, reps=10, calories_burned=60.0,
            )
        )
    session.commit()

    # 1. On Thursday with 0 exercises logged today -> Rest Day
    adeq_rest = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal, today=thursday,
    )
    assert adeq_rest.weekly_progress.trained_days_this_week == 3
    assert adeq_rest.weekly_progress.is_rest_day_eligible is True
    assert adeq_rest.session_action == "rest"
    assert adeq_rest.summary == "Rest Day"
    assert adeq_rest.session_adequacy.is_adequate is False

    # Exercise recommendation on a rest day explicitly says rest day, NOT completed workout
    rec_rest = get_recommendation(
        session=session, user=test_user, rec_type="exercise", today=thursday,
    )
    assert rec_rest.has_recommendation is False
    assert "rest day" in rec_rest.reason.lower()
    assert "completed enough work for this session" not in rec_rest.reason.lower()

    # 2. If the user decides to train on Thursday anyway and logs 1 exercise -> continue_workout (NOT rest)
    session.add(
        Exercise(
            user_id=test_user.id, date=thursday, name="Bench Press", category="strength",
            exercise_catalog_id=bench.id, sets=4, reps=8, calories_burned=80.0,
        )
    )
    session.commit()

    adeq_started = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal, today=thursday,
    )
    assert adeq_started.session_action == "continue_workout"
    assert adeq_started.summary == "Keep Going"


# ──────────────────────────────────────────────────────────────
# TEST 27: Two-day full-body routine evaluates weekly adequacy without requiring every muscle group
# ──────────────────────────────────────────────────────────────

def test_27_two_day_full_body_routine_weekly_adequate(
    session, test_user,
):
    """A valid 2-day full-body routine can achieve weekly 'adequate' status
    without requiring every tracked muscle group (e.g. calves, forearms, abs,
    biceps, triceps) to meet a separate weekly target, while keeping weekly
    progress independent from single-session adequacy."""
    from src.services.training_service import (
        calculate_weekly_targets,
        evaluate_training_adequacy,
    )

    wednesday = date(2026, 11, 4)
    monday = wednesday - timedelta(days=2)

    goal = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        training_days_per_week=2,
    )
    session.add(goal)
    session.commit()

    # Verify frequency-scaled and tiered targets:
    # 2-day intermediate build_muscle: major muscle target_min = 6.0 (10 * 0.6), accessory = 3.0
    targets = calculate_weekly_targets(goal)
    assert targets["chest"][0] == 6.0
    assert targets["back"][0] == 6.0
    assert targets["quadriceps"][0] == 6.0
    assert targets["calves"][0] == 3.0
    assert targets["forearms"][0] == 3.0

    def _catalog(name: str) -> ExerciseCatalogItem:
        return session.exec(
            select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == name)
        ).first()

    squat = _catalog("Barbell Squat")
    bench = _catalog("Bench Press")
    row = _catalog("Barbell Row")
    deadlift = _catalog("Deadlift")
    ohp = _catalog("Overhead Press")
    pullups = _catalog("Pull-ups")

    # Day 1 (Monday): Full Body A — Squat (4 sets), Bench Press (4 sets), Barbell Row (4 sets)
    for item in (squat, bench, row):
        session.add(
            Exercise(
                user_id=test_user.id,
                date=monday,
                name=item.name,
                category="strength",
                exercise_catalog_id=item.id,
                sets=4,
                reps=8,
                calories_burned=90.0,
            )
        )
    session.commit()

    # Evaluate on Monday: Monday's individual session is adequate,
    # BUT weekly progress is still insufficient (only 1 of 2 planned days done).
    adeq_day1 = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal, today=monday,
    )
    assert adeq_day1.session_adequacy.is_adequate is True
    assert adeq_day1.session_action == "workout_adequate"
    assert adeq_day1.weekly_progress.trained_days_this_week == 1
    assert adeq_day1.weekly_progress.overall_status == "insufficient"

    # Day 2 (Wednesday): Full Body B — Deadlift (4 sets), Overhead Press (4 sets), Pull-ups (4 sets)
    for item in (deadlift, ohp, pullups):
        session.add(
            Exercise(
                user_id=test_user.id,
                date=wednesday,
                name=item.name,
                category="strength",
                exercise_catalog_id=item.id,
                sets=4,
                reps=8,
                calories_burned=90.0,
            )
        )
    session.commit()

    # Evaluate on Wednesday: both session and weekly progress are now adequate!
    adeq_day2 = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal, today=wednesday,
    )
    assert adeq_day2.session_adequacy.is_adequate is True
    assert adeq_day2.session_action == "workout_adequate"
    assert adeq_day2.weekly_progress.trained_days_this_week == 2
    assert adeq_day2.weekly_progress.detected_routine == "full_body"
    assert adeq_day2.weekly_progress.core_regions_covered == 3
    assert adeq_day2.weekly_progress.overall_status == "adequate"

    # Confirm that isolated accessories (calves, abs_core, forearms) were NOT required
    muscle_map = adeq_day2.weekly_progress.muscle_volumes
    assert muscle_map["calves"].effective_sets == 0.0
    assert muscle_map["abs_core"].effective_sets == 0.0
    assert muscle_map["forearms"].status == "undertrained"


# ──────────────────────────────────────────────────────────────
# TEST 28: Different training frequencies and routines keep weekly progress meaningful
# ──────────────────────────────────────────────────────────────

def test_28_different_frequencies_and_split_routines_weekly_evaluation(
    session, test_user,
):
    """Weekly evaluation accounts for routine structure and training frequency:
    - A lopsided 2-day routine (only training chest + biceps, neglecting pull/legs)
      remains 'insufficient' even when 2 days are logged.
    - A 4-day Upper/Lower split routine is detected as 'upper_lower' and evaluates
      as 'adequate' when upper and lower days are completed, without requiring
      every accessory muscle to hit a separate target."""
    from src.services.training_service import evaluate_training_adequacy

    friday = date(2026, 11, 6)
    monday = friday - timedelta(days=4)

    def _catalog(name: str) -> ExerciseCatalogItem:
        return session.exec(
            select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == name)
        ).first()

    bench = _catalog("Bench Press")
    pushups = _catalog("Push-ups")
    curl = _catalog("Dumbbell Curl")
    ohp = _catalog("Overhead Press")
    row = _catalog("Barbell Row")
    pullups = _catalog("Pull-ups")
    squat = _catalog("Barbell Squat")
    deadlift = _catalog("Deadlift")
    leg_press = _catalog("Leg Press")

    # Case A: 2-day plan where user only trains chest + biceps on both days (lopsided)
    goal_2day = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        training_days_per_week=2,
    )
    session.add(goal_2day)
    session.commit()

    for offset in (0, 2):  # Monday and Wednesday
        d = monday + timedelta(days=offset)
        for item in (bench, pushups, curl):
            session.add(
                Exercise(
                    user_id=test_user.id,
                    date=d,
                    name=item.name,
                    category="strength",
                    exercise_catalog_id=item.id,
                    sets=4,
                    reps=10,
                    calories_burned=60.0,
                )
            )
    session.commit()

    adeq_lopsided = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal_2day, today=monday + timedelta(days=2),
    )
    # Individual session on Wednesday had 3 exercises, 12 working sets, 2 primary muscles (chest, biceps) -> session adequate
    assert adeq_lopsided.session_adequacy.is_adequate is True
    # But weekly progress is INSUFFICIENT because back (upper_pull) and legs (lower_body) were completely skipped!
    assert adeq_lopsided.weekly_progress.trained_days_this_week == 2
    assert adeq_lopsided.weekly_progress.core_regions_covered == 1
    assert adeq_lopsided.weekly_progress.overall_status == "insufficient"

    # Case B: Clear exercises and test a 4-day Upper/Lower routine (Mon Upper, Tue Lower, Thu Upper, Fri Lower)
    for ex in session.exec(select(Exercise).where(Exercise.user_id == test_user.id)).all():
        session.delete(ex)
    goal_2day.training_days_per_week = 4
    session.add(goal_2day)
    session.commit()

    # Monday & Thursday: Upper Body (Bench Press, Barbell Row, Overhead Press, Pull-ups)
    for offset in (0, 3):
        d = monday + timedelta(days=offset)
        for item in (bench, row, ohp, pullups):
            session.add(
                Exercise(
                    user_id=test_user.id,
                    date=d,
                    name=item.name,
                    category="strength",
                    exercise_catalog_id=item.id,
                    sets=4,
                    reps=8,
                    calories_burned=80.0,
                )
            )

    # Tuesday & Friday: Lower Body (Barbell Squat, Deadlift, Leg Press)
    for offset in (1, 4):
        d = monday + timedelta(days=offset)
        for item in (squat, deadlift, leg_press):
            session.add(
                Exercise(
                    user_id=test_user.id,
                    date=d,
                    name=item.name,
                    category="strength",
                    exercise_catalog_id=item.id,
                    sets=4,
                    reps=8,
                    calories_burned=95.0,
                )
            )
    session.commit()

    adeq_upper_lower = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal_2day, today=friday,
    )
    assert adeq_upper_lower.weekly_progress.trained_days_this_week == 4
    assert adeq_upper_lower.weekly_progress.detected_routine == "upper_lower"
    assert adeq_upper_lower.weekly_progress.core_regions_covered == 3
    assert adeq_upper_lower.weekly_progress.overall_status == "adequate"


# ──────────────────────────────────────────────────────────────
# TEST 29: Recommendations match user available equipment and session context
# ──────────────────────────────────────────────────────────────

def test_29_recommendations_match_equipment_and_session_context(
    session, test_user,
):
    """Recommendations strictly match the user's available equipment and
    maintain session split context (e.g. upper vs lower body)."""
    from src.services.recommendation_service import get_recommendation
    from src.services.training_service import evaluate_training_adequacy

    today = date(2026, 11, 6)

    # 1. Equipment restriction: Dumbbell user only receives dumbbell or bodyweight exercises
    goal_db = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        available_equipment="dumbbell",
    )
    session.add(goal_db)
    session.commit()

    rec_db = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_db.has_recommendation is True
    assert rec_db.items[0].name in ("Dumbbell Curl", "Push-ups", "Plank", "Pull-ups", "Running")
    assert rec_db.items[0].name not in ("Bench Press", "Barbell Squat", "Deadlift", "Barbell Row", "Leg Press")

    # 2. Equipment restriction: "none" user only receives bodyweight exercises
    goal_db.available_equipment = "none"
    session.add(goal_db)
    session.commit()

    rec_none = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_none.has_recommendation is True
    assert rec_none.items[0].name in ("Push-ups", "Plank", "Pull-ups", "Running")
    assert rec_none.items[0].name not in ("Bench Press", "Barbell Squat", "Dumbbell Curl", "Leg Press")

    # 3. Session Context: User with full gym equipment starts an UPPER body workout with Bench Press
    goal_db.available_equipment = "barbell,dumbbell,machines"
    session.add(goal_db)
    session.commit()

    bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    session.add(
        Exercise(
            user_id=test_user.id,
            date=today,
            name="Bench Press",
            category="strength",
            exercise_catalog_id=bench.id,
            sets=3,
            reps=8,
            calories_burned=60.0,
        )
    )
    session.commit()

    # Mid-session recommendation must recommend an upper-body exercise (e.g. Barbell Row or Overhead Press),
    # NEVER a lower body exercise like Barbell Squat or Leg Press
    rec_upper = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_upper.has_recommendation is True
    upper_pick = rec_upper.items[0].name
    assert upper_pick in ("Barbell Row", "Overhead Press", "Pull-ups", "Dumbbell Curl", "Push-ups")
    assert upper_pick not in ("Barbell Squat", "Leg Press", "Deadlift")

    # Training adequacy recommended_next also respects the upper body split context
    adeq = evaluate_training_adequacy(session=session, user_id=test_user.id, goal=goal_db, today=today)
    for next_sugg in adeq.recommended_next:
        assert "Squat" not in next_sugg
        assert "Leg Press" not in next_sugg

    # 4. Session Context: User starts a LOWER body workout with Barbell Squat
    for ex in session.exec(select(Exercise).where(Exercise.user_id == test_user.id)).all():
        session.delete(ex)
    squat = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Barbell Squat")
    ).first()
    session.add(
        Exercise(
            user_id=test_user.id,
            date=today,
            name="Barbell Squat",
            category="strength",
            exercise_catalog_id=squat.id,
            sets=3,
            reps=8,
            calories_burned=75.0,
        )
    )
    session.commit()

    rec_lower = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_lower.has_recommendation is True
    lower_pick = rec_lower.items[0].name
    assert lower_pick in ("Deadlift", "Leg Press")
    assert lower_pick not in ("Bench Press", "Overhead Press", "Barbell Row")


# ──────────────────────────────────────────────────────────────
# TEST 30: Avoid recommending exercises already completed that day
# ──────────────────────────────────────────────────────────────

def test_30_avoid_recommending_exercises_already_completed_that_day(
    session, test_user,
):
    """The engine avoids recommending exercises already completed earlier that day
    across any workout session when suitable alternatives exist in the catalog."""
    from src.services.recommendation_service import get_recommendation

    today = date(2026, 11, 6)
    goal = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        available_equipment="barbell,dumbbell,bodyweight",
    )
    session.add(goal)
    session.commit()

    bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()

    # User completed Bench Press earlier today in Session 1
    session_1 = WorkoutSession(
        user_id=test_user.id,
        date=today,
        status="completed",
        notes="Morning chest",
    )
    session.add(session_1)
    session.flush()

    session.add(
        Exercise(
            user_id=test_user.id,
            date=today,
            name="Bench Press",
            category="strength",
            exercise_catalog_id=bench.id,
            workout_session_id=session_1.id,
            sets=4,
            reps=8,
            calories_burned=80.0,
        )
    )
    session.commit()

    # Later today, user starts Session 2 and asks for a recommendation
    session_2 = WorkoutSession(
        user_id=test_user.id,
        date=today,
        status="active",
        notes="Evening workout",
    )
    session.add(session_2)
    session.commit()

    rec = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec.has_recommendation is True
    # Bench Press must NOT be recommended because it was already completed earlier today
    assert rec.items[0].name != "Bench Press"
    assert rec.items[0].name in ("Barbell Row", "Overhead Press", "Pull-ups", "Barbell Squat", "Deadlift", "Dumbbell Curl")


# ──────────────────────────────────────────────────────────────
# TEST 31: Completion state does not suppress prematurely and recent activity influences selection
# ──────────────────────────────────────────────────────────────

def test_31_completion_state_does_not_suppress_prematurely_and_recency_influences_selection(
    session, test_user,
):
    """Incomplete workouts are not suppressed prematurely, active workouts take
    precedence in general recommendations, and recent training history (yesterday)
    influences exercise selection appropriately."""
    from src.services.recommendation_service import get_recommendation

    today = date(2026, 11, 6)
    yesterday = today - timedelta(days=1)

    goal = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        available_equipment="barbell,dumbbell,bodyweight",
    )
    session.add(goal)

    # 1. User worked back heavily yesterday with Barbell Row
    row = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Barbell Row")
    ).first()
    session.add(
        Exercise(
            user_id=test_user.id,
            date=yesterday,
            name="Barbell Row",
            category="strength",
            exercise_catalog_id=row.id,
            sets=5,
            reps=8,
            calories_burned=100.0,
        )
    )

    # 2. Today, user has logged 1 small exercise (Dumbbell Curl, 2 sets) — incomplete workout
    curl = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Dumbbell Curl")
    ).first()
    session.add(
        Exercise(
            user_id=test_user.id,
            date=today,
            name="Dumbbell Curl",
            category="strength",
            exercise_catalog_id=curl.id,
            sets=2,
            reps=10,
            calories_burned=30.0,
        )
    )
    session.commit()

    # Exercise recommendation must NOT be suppressed (workout is incomplete)
    rec_ex = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_ex.has_recommendation is True
    # Because Barbell Row was performed heavily yesterday, the engine should avoid Barbell Row today
    assert rec_ex.items[0].name != "Barbell Row"
    # Should pick another major compound group that was not worked yesterday (e.g. Bench Press or Barbell Squat)
    assert rec_ex.items[0].name in ("Bench Press", "Barbell Squat", "Overhead Press")

    # In general recommendations (rec_type=None), an active incomplete workout must NOT be
    # prematurely suppressed by meal recommendations (e.g. dinner)
    rec_gen = get_recommendation(session=session, user=test_user, rec_type=None, today=today)
    assert rec_gen.has_recommendation is True
    assert rec_gen.type == "exercise"
    assert rec_gen.items[0].name != "Barbell Row"


# ──────────────────────────────────────────────────────────────
# TEST 32: Effort rating (1-5) known vs unknown in adequacy and progression
# ──────────────────────────────────────────────────────────────

def test_32_effort_rating_known_and_unknown_adequacy_and_progression(
    session, test_user,
):
    """Verify the 1-5 effort rating system across adequacy and progression:
    - Known low effort (1 = Very Easy) discounts working sets so a warm-up-only
      session is not prematurely marked adequate.
    - Known hard effort (4 = Hard, 5 = Extremely Hard) receives full credit.
    - Progression increases weight (+2.5kg) only when effort is known to be
      manageable (1-4) and target reps are met; unknown effort (None) or
      Extremely Hard (5) keeps the same weight without treating unknown effort
      as a known rating."""
    from src.services.recommendation_service import get_recommendation
    from src.services.training_service import (
        EFFORT_RATING_DESCRIPTIONS,
        EFFORT_RATING_LABELS,
        evaluate_training_adequacy,
    )

    assert EFFORT_RATING_LABELS == {
        1: "Very Easy",
        2: "Easy",
        3: "Moderate",
        4: "Hard",
        5: "Extremely Hard",
    }
    assert len(EFFORT_RATING_DESCRIPTIONS) == 5

    today = date(2026, 11, 6)
    three_days_ago = today - timedelta(days=3)

    goal = UserGoal(
        user_id=test_user.id,
        goal_type="build_muscle",
        training_experience="intermediate",
        available_equipment="barbell",
    )
    session.add(goal)
    session.commit()

    def _cat(name: str) -> ExerciseCatalogItem:
        return session.exec(
            select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == name)
        ).first()

    bench = _cat("Bench Press")
    row = _cat("Barbell Row")
    ohp = _cat("Overhead Press")

    # 1. Session with 3 exercises (3 sets each = 9 raw sets), all rated 1 (Very Easy -> 0.5x multiplier = 4.5 working sets)
    # Must NOT be marked adequate for intermediate (requires >= 8.0 working sets)
    for item in (bench, row, ohp):
        session.add(
            Exercise(
                user_id=test_user.id,
                date=today,
                name=item.name,
                category="strength",
                exercise_catalog_id=item.id,
                sets=3,
                reps=8,
                weight_kg=50.0,
                effort_rating=1,  # Very Easy
                calories_burned=50.0,
            )
        )
    session.commit()

    adeq_very_easy = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal, today=today,
    )
    assert adeq_very_easy.session_adequacy.is_adequate is False
    assert adeq_very_easy.session_action == "continue_workout"

    # 2. Update effort_rating to 4 (Hard -> 1.0x multiplier = 9.0 working sets) -> now adequate!
    for ex in session.exec(select(Exercise).where(Exercise.user_id == test_user.id)).all():
        ex.effort_rating = 4
        session.add(ex)
    session.commit()

    adeq_hard = evaluate_training_adequacy(
        session=session, user_id=test_user.id, goal=goal, today=today,
    )
    assert adeq_hard.session_adequacy.is_adequate is True
    assert adeq_hard.session_action == "workout_adequate"

    # 3. Progression check with unknown effort (None) vs known effort (3 Moderate vs 5 Extremely Hard)
    for ex in session.exec(select(Exercise).where(Exercise.user_id == test_user.id)).all():
        session.delete(ex)
    session.commit()

    # Log Bench Press 3 days ago with unknown effort (effort_rating=None), weight=70kg, reps=8
    hist_ex = Exercise(
        user_id=test_user.id,
        date=three_days_ago,
        name="Bench Press",
        category="strength",
        exercise_catalog_id=bench.id,
        sets=4,
        reps=8,
        weight_kg=70.0,
        effort_rating=None,  # Unknown effort
        calories_burned=80.0,
    )
    session.add(hist_ex)
    # Log Squat and Row 3 days ago so Bench Press (chest) is the top recommendation today
    for other_name in ("Barbell Squat", "Barbell Row", "Deadlift", "Overhead Press"):
        c_item = _cat(other_name)
        session.add(
            Exercise(
                user_id=test_user.id,
                date=three_days_ago,
                name=c_item.name,
                category="strength",
                exercise_catalog_id=c_item.id,
                sets=6,
                reps=8,
                weight_kg=80.0,
                effort_rating=4,
                calories_burned=90.0,
            )
        )
    session.commit()

    # Unknown effort (None): must NOT treat unknown effort as a known manageable value -> keeps 70.0 kg
    rec_unknown = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_unknown.items[0].name == "Bench Press"
    assert rec_unknown.items[0].weight_kg == 70.0
    assert "(" not in (rec_unknown.items[0].last_performance or "")

    # Known effort = 3 (Moderate): manageable effort + met target reps -> progresses to 72.5 kg
    hist_ex.effort_rating = 3
    session.add(hist_ex)
    session.commit()

    rec_moderate = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_moderate.items[0].name == "Bench Press"
    assert rec_moderate.items[0].weight_kg == 72.5
    assert "(Moderate)" in (rec_moderate.items[0].last_performance or "")

    # Known effort = 5 (Extremely Hard): near max effort -> keeps 70.0 kg
    hist_ex.effort_rating = 5
    session.add(hist_ex)
    session.commit()

    rec_max = get_recommendation(session=session, user=test_user, rec_type="exercise", today=today)
    assert rec_max.items[0].name == "Bench Press"
    assert rec_max.items[0].weight_kg == 70.0
    assert "(Extremely Hard)" in (rec_max.items[0].last_performance or "")


# ──────────────────────────────────────────────────────────────
# TEST 33: Historical records without effort_rating remain valid
# ──────────────────────────────────────────────────────────────

def test_33_historical_records_without_effort_rating_remain_valid(
    session, test_user,
):
    """Historical exercise records with effort_rating=None remain valid across
    router serialization, history lookups, and adequacy evaluation without
    inventing synthetic effort ratings."""
    from src.routers.exercises import create_exercise, get_exercise_history, get_exercises, update_exercise
    from src.schemas import ExerciseLogCreate, ExerciseLogUpdate

    today = date(2026, 11, 6)
    legacy = Exercise(
        user_id=test_user.id,
        date=today - timedelta(days=5),
        name="Bench Press",
        category="strength",
        sets=4,
        reps=8,
        weight_kg=65.0,
        effort_rating=None,
        calories_burned=75.0,
    )
    session.add(legacy)
    session.commit()

    all_logs = get_exercises(session=session, current_user=test_user)
    assert len(all_logs) == 1
    assert all_logs[0].effort_rating is None

    hist = get_exercise_history(session=session, current_user=test_user, name="Bench Press")
    assert hist.last is not None
    assert hist.last.effort_rating is None

    # Creating and updating an exercise with effort_rating (1-5) works end-to-end
    created = create_exercise(
        ExerciseLogCreate(
            date=today,
            name="Bench Press",
            category="strength",
            sets=4,
            reps=8,
            weight_kg=67.5,
            effort_rating=4,
        ),
        session=session,
        current_user=test_user,
    )
    assert created.effort_rating == 4

    updated = update_exercise(
        exercise_id=created.id,
        exercise_data=ExerciseLogUpdate(effort_rating=5),
        session=session,
        current_user=test_user,
    )
    assert updated.effort_rating == 5


# ──────────────────────────────────────────────────────────────
# TEST 34: Strength progression based on comparable history and trends
# ──────────────────────────────────────────────────────────────

def test_34_strength_progression_comparable_history_and_trends(
    session, test_user,
):
    """Verify conservative, explainable strength progression:
    - Non-comparable logs (e.g. 1RM singles or 25-rep warmups) do not produce
      unjustified progression.
    - When a comparable log exists alongside a newer non-comparable outlier,
      progression uses the comparable working log.
    - Incomplete set counts or stale history (>21 days) hold weight.
    - Recent Hard (4) load jumps consolidate before progressing again.
    - Consecutive missed targets trigger a conservative deload (-2.5 kg).
    - Light / isolation lifts use a smaller conservative increment (+1.0 kg)."""
    from src.services.recommendation_service import (
        _get_valid_exercise_history,
        _prescribe_weighted_strength,
    )
    from src.services.training_service import get_muscle_mappings

    today = date(2026, 11, 6)
    mappings = get_muscle_mappings(session)

    bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    curl = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Dumbbell Curl")
    ).first()
    bench_mappings = mappings.get(bench.id, [])
    curl_mappings = mappings.get(curl.id, [])

    # 1. Only non-comparable 1RM test (100 kg x 1) -> no load prescribed, clear explanation
    one_rm = Exercise(
        user_id=test_user.id,
        date=today - timedelta(days=2),
        name="Bench Press",
        category="strength",
        exercise_catalog_id=bench.id,
        sets=1,
        reps=1,
        weight_kg=100.0,
        effort_rating=5,
        calories_burned=20.0,
    )
    session.add(one_rm)
    session.commit()

    logs = _get_valid_exercise_history(session, test_user.id, bench, today)
    sets, reps, rest_s, w_kg, last_perf, note = _prescribe_weighted_strength(
        bench, bench_mappings, "build_muscle", "intermediate", logs, today,
    )
    assert (sets, reps, rest_s) == (4, 8, 120)
    assert w_kg is None
    assert "non-comparable" in (note or "").lower()

    # 2. Comparable working log (70 kg x 8, effort 3) 4 days ago + 1RM test 2 days ago
    # -> skips the 1RM outlier and progresses from comparable 70 kg -> 72.5 kg
    comp_log = Exercise(
        user_id=test_user.id,
        date=today - timedelta(days=4),
        name="Bench Press",
        category="strength",
        exercise_catalog_id=bench.id,
        sets=4,
        reps=8,
        weight_kg=70.0,
        effort_rating=3,
        calories_burned=80.0,
    )
    session.add(comp_log)
    session.commit()

    logs = _get_valid_exercise_history(session, test_user.id, bench, today)
    _, _, _, w_kg, last_perf, note = _prescribe_weighted_strength(
        bench, bench_mappings, "build_muscle", "intermediate", logs, today,
    )
    assert w_kg == 72.5
    assert "70 kg x 8" in (last_perf or "")
    assert "+2.5 kg" in (note or "")

    # 3. Incomplete working sets (1 set x 8 reps @ 70 kg) -> holds 70.0 kg
    comp_log.sets = 1
    session.add(comp_log)
    session.commit()

    logs = _get_valid_exercise_history(session, test_user.id, bench, today)
    _, _, _, w_kg, _, note = _prescribe_weighted_strength(
        bench, bench_mappings, "build_muscle", "intermediate", logs, today,
    )
    assert w_kg == 70.0
    assert "working sets" in (note or "").lower()

    # 4. Stale comparable history (30 days ago) -> holds 70.0 kg conservatively
    comp_log.sets = 4
    comp_log.date = today - timedelta(days=30)
    session.add(comp_log)
    session.commit()

    logs = _get_valid_exercise_history(session, test_user.id, bench, today)
    _, _, _, w_kg, _, note = _prescribe_weighted_strength(
        bench, bench_mappings, "build_muscle", "intermediate", logs, today,
    )
    assert w_kg == 70.0
    assert "30 days ago" in (note or "")

    # 5. Trend consolidation: jumped from 70.0 kg (6 days ago) to 72.5 kg (3 days ago) at Hard (4) effort
    # -> holds 72.5 kg to consolidate the recent jump before adding more weight
    comp_log.date = today - timedelta(days=6)
    comp_log.weight_kg = 70.0
    comp_log.reps = 8
    comp_log.effort_rating = 3
    recent_jump = Exercise(
        user_id=test_user.id,
        date=today - timedelta(days=3),
        name="Bench Press",
        category="strength",
        exercise_catalog_id=bench.id,
        sets=4,
        reps=8,
        weight_kg=72.5,
        effort_rating=4,  # Hard
        calories_burned=85.0,
    )
    session.add_all([comp_log, recent_jump])
    session.commit()

    logs = _get_valid_exercise_history(session, test_user.id, bench, today)
    _, _, _, w_kg, _, note = _prescribe_weighted_strength(
        bench, bench_mappings, "build_muscle", "intermediate", logs, today,
    )
    assert w_kg == 72.5
    assert "consolidating" in (note or "").lower()

    # 6. Consecutive missed targets at 72.5 kg (6 reps then 5 reps, effort 5) -> deloads to 70.0 kg
    comp_log.weight_kg = 72.5
    comp_log.reps = 6
    comp_log.effort_rating = 5
    recent_jump.weight_kg = 72.5
    recent_jump.reps = 5
    recent_jump.effort_rating = 5
    session.add_all([comp_log, recent_jump])
    session.commit()

    logs = _get_valid_exercise_history(session, test_user.id, bench, today)
    _, _, _, w_kg, _, note = _prescribe_weighted_strength(
        bench, bench_mappings, "build_muscle", "intermediate", logs, today,
    )
    assert w_kg == 70.0
    assert "reducing load" in (note or "").lower()

    # 7. Isolation exercise with light load (Dumbbell Curl @ 10 kg x 12, effort 3)
    # -> prescribes isolation sets/reps/rest (3 x 12, 75s rest) and +1.0 kg step (11.0 kg)
    curl_log = Exercise(
        user_id=test_user.id,
        date=today - timedelta(days=3),
        name="Dumbbell Curl",
        category="strength",
        exercise_catalog_id=curl.id,
        sets=3,
        reps=12,
        weight_kg=10.0,
        effort_rating=3,
        calories_burned=40.0,
    )
    session.add(curl_log)
    session.commit()

    curl_logs = _get_valid_exercise_history(session, test_user.id, curl, today)
    c_sets, c_reps, c_rest, c_w, _, c_note = _prescribe_weighted_strength(
        curl, curl_mappings, "build_muscle", "intermediate", curl_logs, today,
    )
    assert (c_sets, c_reps, c_rest) == (3, 12, 75)
    assert c_w == 11.0
    assert "+1 kg" in (c_note or "")


# ──────────────────────────────────────────────────────────────
# TEST 35: Unknown effort never produces unjustified progression
# ──────────────────────────────────────────────────────────────

def test_35_unknown_effort_never_produces_unjustified_progression(
    session, test_user,
):
    """Even when a user logs multiple consecutive sessions meeting target sets,
    reps, or duration, unknown effort (effort_rating=None) never triggers
    load, rep, or duration progression across strength, bodyweight, or cardio."""
    from src.services.recommendation_service import (
        _get_valid_exercise_history,
        _prescribe_bodyweight_strength,
        _prescribe_cardio,
        _prescribe_weighted_strength,
    )
    from src.services.training_service import get_muscle_mappings

    today = date(2026, 11, 6)
    mappings = get_muscle_mappings(session)

    bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    pushups = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Push-ups")
    ).first()
    running = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Running")
    ).first()

    # Log 3 consecutive sessions of Bench Press (80 kg x 10), Push-ups (3 x 14), Running (30 min)
    # all with effort_rating=None
    for d_offset in (6, 4, 2):
        d = today - timedelta(days=d_offset)
        session.add_all([
            Exercise(
                user_id=test_user.id,
                date=d,
                name="Bench Press",
                category="strength",
                exercise_catalog_id=bench.id,
                sets=4,
                reps=10,
                weight_kg=80.0,
                effort_rating=None,
                calories_burned=90.0,
            ),
            Exercise(
                user_id=test_user.id,
                date=d,
                name="Push-ups",
                category="strength",
                exercise_catalog_id=pushups.id,
                sets=3,
                reps=14,
                effort_rating=None,
                calories_burned=45.0,
            ),
            Exercise(
                user_id=test_user.id,
                date=d,
                name="Running",
                category="cardio",
                exercise_catalog_id=running.id,
                duration_minutes=30,
                effort_rating=None,
                calories_burned=250.0,
            ),
        ])
    session.commit()

    # Weighted strength: stays at 80.0 kg (never 82.5 kg)
    b_logs = _get_valid_exercise_history(session, test_user.id, bench, today)
    _, _, _, b_weight, _, b_note = _prescribe_weighted_strength(
        bench, mappings.get(bench.id, []), "build_muscle", "intermediate", b_logs, today,
    )
    assert b_weight == 80.0
    assert "effort rating was not recorded" in (b_note or "").lower()

    # Bodyweight strength: stays at 14 reps (never progresses to 16)
    p_logs = _get_valid_exercise_history(session, test_user.id, pushups, today)
    p_sets, p_reps, _, _, _, p_note = _prescribe_bodyweight_strength(
        pushups, "intermediate", p_logs, today,
    )
    assert p_sets == 3
    assert p_reps == 14
    assert "unknown" in (p_note or "").lower()

    # Cardio: stays at 30 min (never progresses to 35 min for build_muscle)
    r_logs = _get_valid_exercise_history(session, test_user.id, running, today)
    r_dur, _, _, r_note = _prescribe_cardio(
        running, "build_muscle", "intermediate", r_logs, today,
    )
    assert r_dur == 30
    assert r_note is None


# ──────────────────────────────────────────────────────────────
# TEST 36: Cardio and bodyweight prescriptions stay within reasonable bounds
# ──────────────────────────────────────────────────────────────

def test_36_cardio_and_bodyweight_prescriptions_stay_within_reasonable_bounds(
    session, test_user,
):
    """Cardio and bodyweight prescriptions stay within reasonable bounds
    even when historical records have extreme low or high values, and
    include appropriate duration, sets, reps, and rest recommendations."""
    from src.services.recommendation_service import (
        BODYWEIGHT_HARD_REP_BOUNDS,
        BODYWEIGHT_HOLD_DURATION_BOUNDS,
        BODYWEIGHT_SETS_BOUNDS,
        BODYWEIGHT_STANDARD_REP_BOUNDS,
        CARDIO_HIIT_DURATION_BOUNDS,
        CARDIO_STEADY_DURATION_BOUNDS,
        _get_valid_exercise_history,
        _prescribe_bodyweight_strength,
        _prescribe_cardio,
    )

    today = date(2026, 11, 6)

    pushups = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Push-ups")
    ).first()
    pullups = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Pull-ups")
    ).first()
    plank = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Plank")
    ).first()
    running = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Running")
    ).first()
    hiit = ExerciseCatalogItem(
        name="HIIT",
        category="cardio",
        default_met=8.0,
        equipment="bodyweight",
        level="intermediate",
        description="High-Intensity Interval Training",
    )
    session.add(hiit)
    session.commit()
    session.refresh(hiit)

    # 1. Isometric bodyweight hold (Plank): bounded sets (2-4), reps=1, duration (1-3 min), rest=60s
    for exp in ("beginner", "intermediate", "advanced"):
        s, r, dur, rest_s, _, _ = _prescribe_bodyweight_strength(plank, exp, [], today)
        assert BODYWEIGHT_SETS_BOUNDS[0] <= s <= BODYWEIGHT_SETS_BOUNDS[1]
        assert r == 1
        assert dur is not None and BODYWEIGHT_HOLD_DURATION_BOUNDS[0] <= dur <= BODYWEIGHT_HOLD_DURATION_BOUNDS[1]
        assert rest_s == 60

    # 2. Extreme high bodyweight log (Push-ups: 10 sets x 100 reps, effort=1)
    # -> clamped strictly to BODYWEIGHT_SETS_BOUNDS (<=4) and BODYWEIGHT_STANDARD_REP_BOUNDS (<=20)
    session.add(
        Exercise(
            user_id=test_user.id,
            date=today - timedelta(days=2),
            name="Push-ups",
            category="strength",
            exercise_catalog_id=pushups.id,
            sets=10,
            reps=100,
            effort_rating=1,
            calories_burned=100.0,
        )
    )
    # 3. Extreme low Pull-ups log (1 set x 1 rep, effort=5)
    # -> clamped strictly to >= BODYWEIGHT_SETS_BOUNDS[0] (2) and >= BODYWEIGHT_HARD_REP_BOUNDS[0] (4)
    session.add(
        Exercise(
            user_id=test_user.id,
            date=today - timedelta(days=2),
            name="Pull-ups",
            category="strength",
            exercise_catalog_id=pullups.id,
            sets=1,
            reps=1,
            effort_rating=5,
            calories_burned=10.0,
        )
    )
    # 4. Extreme cardio logs: Running 180 min (effort=1) and HIIT 90 min (effort=1)
    session.add_all([
        Exercise(
            user_id=test_user.id,
            date=today - timedelta(days=2),
            name="Running",
            category="cardio",
            exercise_catalog_id=running.id,
            duration_minutes=180,
            effort_rating=1,
            calories_burned=1200.0,
        ),
        Exercise(
            user_id=test_user.id,
            date=today - timedelta(days=2),
            name="HIIT",
            category="cardio",
            exercise_catalog_id=hiit.id,
            duration_minutes=90,
            effort_rating=1,
            calories_burned=800.0,
        ),
    ])
    session.commit()

    push_logs = _get_valid_exercise_history(session, test_user.id, pushups, today)
    ps, pr, pdur, prest, _, _ = _prescribe_bodyweight_strength(pushups, "intermediate", push_logs, today)
    assert BODYWEIGHT_SETS_BOUNDS[0] <= ps <= BODYWEIGHT_SETS_BOUNDS[1]
    assert BODYWEIGHT_STANDARD_REP_BOUNDS[0] <= pr <= BODYWEIGHT_STANDARD_REP_BOUNDS[1]
    assert pdur is None
    assert prest == 60

    pull_logs = _get_valid_exercise_history(session, test_user.id, pullups, today)
    ulls, ullr, _, ullrest, _, _ = _prescribe_bodyweight_strength(pullups, "intermediate", pull_logs, today)
    assert BODYWEIGHT_SETS_BOUNDS[0] <= ulls <= BODYWEIGHT_SETS_BOUNDS[1]
    assert BODYWEIGHT_HARD_REP_BOUNDS[0] <= ullr <= BODYWEIGHT_HARD_REP_BOUNDS[1]
    assert ullrest == 90

    run_logs = _get_valid_exercise_history(session, test_user.id, running, today)
    run_dur, run_rest, _, _ = _prescribe_cardio(running, "improve_endurance", "advanced", run_logs, today)
    assert CARDIO_STEADY_DURATION_BOUNDS[0] <= run_dur <= CARDIO_STEADY_DURATION_BOUNDS[1]
    assert run_rest is None

    hiit_logs = _get_valid_exercise_history(session, test_user.id, hiit, today)
    hiit_dur, hiit_rest, _, _ = _prescribe_cardio(hiit, "lose_weight", "advanced", hiit_logs, today)
    assert CARDIO_HIIT_DURATION_BOUNDS[0] <= hiit_dur <= CARDIO_HIIT_DURATION_BOUNDS[1]
    assert hiit_rest == 60








