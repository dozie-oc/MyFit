"""
Tests for Goal Onboarding and Deterministic Recommendation Engine.

Covers all 14 required states:
1. New user without a goal.
2. New user completes goal onboarding.
3. Existing user with goal.
4. No meals/exercises today.
5. Breakfast logged.
6. Breakfast + lunch logged.
7. Exercise logged.
8. Same exercise already logged.
9. Nutrition nearly complete.
10. Nutrition + exercise complete.
11. Equipment restriction.
12. Dietary restriction.
13. Recommendation action.
14. Meal/exercise mutation followed by recommendation refresh.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from src.auth.auth import create_access_token, hash_password
from src.database import get_session
from src.main import app
from src.models import ExerciseCatalogItem, FoodItem, User


from tests.conftest import make_test_engine


test_engine = make_test_engine()


@pytest.fixture
def session():
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        # Populate exercise catalog
        catalog = [
            ExerciseCatalogItem(name="Running", category="cardio", default_met=9.8, description="Outdoor running"),
            ExerciseCatalogItem(name="Push-ups", category="strength", default_met=4.5, description="Bodyweight push-ups"),
            ExerciseCatalogItem(name="Plank", category="strength", default_met=3.5, description="Isometric core plank"),
            ExerciseCatalogItem(name="Bench Press", category="strength", default_met=5.0, description="Barbell bench press"),
            ExerciseCatalogItem(name="Barbell Squat", category="strength", default_met=5.0, description="Barbell squats"),
            ExerciseCatalogItem(name="Dumbbell Curl", category="strength", default_met=4.5, description="Dumbbell curls"),
            ExerciseCatalogItem(name="Leg Press", category="strength", default_met=5.0, description="Machine leg press"),
        ]
        session.add_all(catalog)

        # Populate basic foods
        foods = [
            FoodItem(name="Oatmeal", calories_per_100g=389.0, protein_per_100g=16.9, carbs_per_100g=66.3, fat_per_100g=6.9, base_unit="g"),
            FoodItem(name="Banana", calories_per_100g=89.0, protein_per_100g=1.1, carbs_per_100g=22.8, fat_per_100g=0.3, base_unit="g"),
            FoodItem(name="Chicken Breast", calories_per_100g=165.0, protein_per_100g=31.0, carbs_per_100g=0.0, fat_per_100g=3.6, base_unit="g"),
            FoodItem(name="Brown Rice", calories_per_100g=111.0, protein_per_100g=2.6, carbs_per_100g=23.0, fat_per_100g=0.9, base_unit="g"),
            FoodItem(name="Greek Yogurt", calories_per_100g=59.0, protein_per_100g=10.0, carbs_per_100g=3.6, fat_per_100g=0.4, base_unit="g"),
            FoodItem(name="Salmon Fillet", calories_per_100g=208.0, protein_per_100g=20.4, carbs_per_100g=0.0, fat_per_100g=13.4, base_unit="g"),
            FoodItem(name="Boiled Egg", calories_per_100g=155.0, protein_per_100g=12.6, carbs_per_100g=1.1, fat_per_100g=10.6, base_unit="g"),
        ]
        session.add_all(foods)
        session.commit()

        yield session

    SQLModel.metadata.drop_all(test_engine)


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
        username="recuser",
        hashed_password=hash_password("Password123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 5, 20),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, test_user):
    response = client.post(
        "/auth/login",
        json={
            "username": "recuser",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_1_new_user_without_goal(client, auth_headers):
    """1. New user without a goal returns null id/goal_type."""
    res = client.get("/goals", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] is None
    assert data["goal_type"] is None


def test_2_and_3_onboarding_and_existing_goal(client, auth_headers):
    """2. New user completes goal onboarding. 3. Existing user with goal."""
    goal_data = {
        "goal_type": "build_muscle",
        "target_weight": 75.0,
        "activity_level": "moderately_active",
        "training_days_per_week": 4,
        "training_experience": "intermediate",
        "available_equipment": "barbell,dumbbell,bodyweight",
        "dietary_preference": "omnivore",
        "foods_to_avoid": "salmon",
    }
    # 2. Complete onboarding
    create_res = client.post("/goals", json=goal_data, headers=auth_headers)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] is not None
    assert created["goal_type"] == "build_muscle"

    # 3. Existing user with goal
    get_res = client.get("/goals", headers=auth_headers)
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["id"] == created["id"]
    assert retrieved["goal_type"] == "build_muscle"
    assert retrieved["available_equipment"] == "barbell,dumbbell,bodyweight"


def test_goal_partial_update_preserves_other_fields(client, auth_headers):
    """Regression: updating one field must not wipe the others."""
    client.post(
        "/goals",
        json={
            "goal_type": "build_muscle",
            "training_days_per_week": 4,
            "training_experience": "intermediate",
            "foods_to_avoid": "salmon",
        },
        headers=auth_headers,
    )

    res = client.post(
        "/goals", json={"goal_type": "lose_weight"}, headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["goal_type"] == "lose_weight"
    assert data["training_days_per_week"] == 4
    assert data["training_experience"] == "intermediate"
    assert data["foods_to_avoid"] == "salmon"

    # An explicit null still clears a field.
    res = client.post(
        "/goals", json={"foods_to_avoid": None}, headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json()["foods_to_avoid"] is None
    assert res.json()["goal_type"] == "lose_weight"


def test_summary_get_does_not_persist(client, session, auth_headers):
    """Regression: GET /summary/{date} must be read-only."""
    from sqlmodel import select
    from src.models import DailySummary

    today_str = date.today().isoformat()

    for _ in range(2):
        res = client.get(f"/summary/{today_str}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["calories_in"] == 0
        assert data["calories_out"] == 0

    assert session.exec(select(DailySummary)).all() == []


def test_summary_updates_after_meal_is_logged(client, session, auth_headers):
    """The write path still keeps the cached summary fresh."""
    from sqlmodel import select

    egg = session.exec(
        select(FoodItem).where(FoodItem.name == "Boiled Egg")
    ).first()
    today_str = date.today().isoformat()

    client.post(
        "/meals",
        json={
            "date": today_str,
            "meal_type": "breakfast",
            "items": [{"food_id": egg.id, "quantity": 100.0, "unit": "g"}],
        },
        headers=auth_headers,
    )

    res = client.get(f"/summary/{today_str}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["calories_in"] == 155


def test_4_no_meals_no_exercises_recommends_breakfast(client, auth_headers):
    """4. When nothing is logged today, recommends Breakfast."""
    res = client.get("/recommendations/today", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["has_recommendation"] is True
    assert data["type"] == "meal"
    assert data["meal_type"] == "breakfast"
    assert "Breakfast" in data["title"]


def test_5_breakfast_logged_no_breakfast_again(client, session, auth_headers):
    """5. Once breakfast is logged, never recommend breakfast again; recommends exercise or lunch."""
    # Find food id
    from sqlmodel import select
    egg = session.exec(select(FoodItem).where(FoodItem.name == "Boiled Egg")).first()

    today_str = date.today().isoformat()
    client.post(
        "/meals",
        json={
            "date": today_str,
            "meal_type": "breakfast",
            "items": [{"food_id": egg.id, "quantity": 100.0, "unit": "g"}],
        },
        headers=auth_headers,
    )

    # General recommendation should now recommend Exercise (workout of the day)
    res = client.get("/recommendations/today", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["has_recommendation"] is True
    # Can be exercise because breakfast is eaten and user hasn't worked out yet
    assert data["type"] == "exercise"

    # And if explicitly asking for meal, must be LUNCH, NOT breakfast!
    meal_res = client.get("/recommendations/today?type=meal", headers=auth_headers)
    assert meal_res.status_code == 200
    meal_data = meal_res.json()
    assert meal_data["meal_type"] == "lunch"
    assert "Lunch" in meal_data["title"]


def test_6_breakfast_and_lunch_logged_recommends_dinner_or_exercise(client, session, auth_headers):
    """6. Breakfast + Lunch logged -> neither breakfast nor lunch is recommended."""
    from sqlmodel import select
    egg = session.exec(select(FoodItem).where(FoodItem.name == "Boiled Egg")).first()
    chicken = session.exec(select(FoodItem).where(FoodItem.name == "Chicken Breast")).first()
    today_str = date.today().isoformat()

    client.post(
        "/meals",
        json={
            "date": today_str,
            "meal_type": "breakfast",
            "items": [{"food_id": egg.id, "quantity": 100.0, "unit": "g"}],
        },
        headers=auth_headers,
    )
    client.post(
        "/meals",
        json={
            "date": today_str,
            "meal_type": "lunch",
            "items": [{"food_id": chicken.id, "quantity": 150.0, "unit": "g"}],
        },
        headers=auth_headers,
    )

    # Meal recommendation must now be dinner!
    meal_res = client.get("/recommendations/today?type=meal", headers=auth_headers)
    assert meal_res.status_code == 200
    meal_data = meal_res.json()
    assert meal_data["meal_type"] == "dinner"
    assert "Dinner" in meal_data["title"]


def test_7_and_8_exercise_completion_and_no_duplicate(client, session, auth_headers):
    """7. One exercise logged does NOT mark workout complete. 8. Never recommend same exercise already logged."""
    today_str = date.today().isoformat()
    # Log Push-ups
    client.post(
        "/exercises",
        json={
            "date": today_str,
            "name": "Push-ups",
            "category": "strength",
            "sets": 3,
            "reps": 10,
            "intensity": "moderate",
        },
        headers=auth_headers,
    )

    # Check exercise-specific recommendation: single exercise is NOT enough.
    # The system should recommend MORE exercises ("keep going").
    ex_res = client.get("/recommendations/today?type=exercise", headers=auth_headers)
    assert ex_res.status_code == 200
    ex_data = ex_res.json()
    assert ex_data["has_recommendation"] is True
    # The recommended exercise must NOT be Push-ups (already logged)
    rec_name = ex_data["items"][0]["name"]
    assert rec_name != "Push-ups"


def test_9_nutrition_nearly_complete(client, session, auth_headers):
    """9. When nutrition is nearly complete, avoid huge meal."""
    from sqlmodel import select
    oat = session.exec(select(FoodItem).where(FoodItem.name == "Oatmeal")).first()
    today_str = date.today().isoformat()

    # User goal: maintain_weight (cal target ~ 2450 kcal)
    client.post(
        "/goals",
        json={"goal_type": "maintain_weight", "activity_level": "moderately_active"},
        headers=auth_headers,
    )

    # Log meals bringing calories to 2350 (only ~100 kcal left)
    client.post(
        "/meals",
        json={
            "date": today_str,
            "meal_type": "breakfast",
            "items": [{"food_id": oat.id, "quantity": 600.0, "unit": "g"}],
        },
        headers=auth_headers,
    )

    meal_res = client.get("/recommendations/today?type=meal", headers=auth_headers)
    assert meal_res.status_code == 200
    data = meal_res.json()
    # With cal_remaining < MIN_CALORIE_REMAINING, target is on track!
    assert data["has_recommendation"] is False
    assert "track" in data["reason"].lower() or "consumed" in data["reason"].lower()


def test_10_nutrition_and_exercise_complete(client, session, auth_headers):
    """10. Nutrition + exercise both complete -> returns all set.
    
    Must log ENOUGH exercises to satisfy the training adequacy system.
    A single cardio run is no longer sufficient to mark the workout as done.
    """
    from sqlmodel import select
    oat = session.exec(select(FoodItem).where(FoodItem.name == "Oatmeal")).first()
    today_str = date.today().isoformat()

    client.post(
        "/goals",
        json={
            "goal_type": "maintain_weight",
            "activity_level": "moderately_active",
            "training_days_per_week": 3,
            "training_experience": "beginner",
        },
        headers=auth_headers,
    )
    # Log multiple exercises to reach workout_adequate status for a beginner
    exercises = [
        {"date": today_str, "name": "Running", "category": "cardio", "duration_minutes": 30},
        {"date": today_str, "name": "Push-ups", "category": "strength", "sets": 3, "reps": 10},
        {"date": today_str, "name": "Plank", "category": "strength", "sets": 3, "reps": 1, "duration_minutes": 1},
        {"date": today_str, "name": "Bench Press", "category": "strength", "sets": 3, "reps": 10},
        {"date": today_str, "name": "Barbell Squat", "category": "strength", "sets": 3, "reps": 10},
        {"date": today_str, "name": "Dumbbell Curl", "category": "strength", "sets": 3, "reps": 10},
    ]
    for ex in exercises:
        client.post("/exercises", json=ex, headers=auth_headers)

    # Log enough calories
    client.post(
        "/meals",
        json={"date": today_str, "meal_type": "dinner", "items": [{"food_id": oat.id, "quantity": 650.0, "unit": "g"}]},
        headers=auth_headers,
    )

    res = client.get("/recommendations/today", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["has_recommendation"] is False
    assert "all set" in data["reason"].lower() or "track" in data["reason"].lower()


def test_11_equipment_restriction(client, auth_headers):
    """11. Equipment restriction: bodyweight/none user never gets barbell or machine exercises."""
    client.post(
        "/goals",
        json={
            "goal_type": "build_muscle",
            "available_equipment": "none",
        },
        headers=auth_headers,
    )
    res = client.get("/recommendations/today?type=exercise", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["has_recommendation"] is True
    rec_name = data["items"][0]["name"]
    # Must be bodyweight (Push-ups or Plank or Running), NOT Bench Press or Barbell Squat or Leg Press
    assert rec_name in ("Push-ups", "Plank", "Running")
    assert rec_name not in ("Bench Press", "Barbell Squat", "Leg Press", "Dumbbell Curl")


def test_12_dietary_restriction(client, auth_headers):
    """12. Dietary restriction: vegan gets no meat/eggs/dairy, vegetarian gets no meat/fish."""
    # Vegan
    client.post(
        "/goals",
        json={"dietary_preference": "vegan", "foods_to_avoid": "apple"},
        headers=auth_headers,
    )
    res = client.get("/recommendations/today?type=meal", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    rec_names = [it["name"] for it in data["items"]]
    for name in rec_names:
        assert "Chicken" not in name
        assert "Salmon" not in name
        assert "Egg" not in name
        assert "Yogurt" not in name

    # Vegetarian
    client.post(
        "/goals",
        json={"dietary_preference": "vegetarian"},
        headers=auth_headers,
    )
    res_veg = client.get("/recommendations/today?type=meal", headers=auth_headers)
    assert res_veg.status_code == 200
    veg_names = [it["name"] for it in res_veg.json()["items"]]
    for name in veg_names:
        assert "Chicken" not in name
        assert "Salmon" not in name


def test_13_and_14_recommendation_action_and_refresh(client, session, auth_headers):
    """13. Recommendation action creates meal directly. 14. Mutation causes recommendation state to update."""
    today_str = date.today().isoformat()

    # Step 1: Get breakfast recommendation
    res1 = client.get("/recommendations/today", headers=auth_headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["type"] == "meal"
    assert data1["meal_type"] == "breakfast"

    # Step 2: User executes the action to log recommended items
    payload_items = [
        {"food_id": it["food_id"], "quantity": it["quantity"], "unit": it["unit"]}
        for it in data1["items"]
    ]
    log_res = client.post(
        "/meals",
        json={
            "date": today_str,
            "meal_type": data1["meal_type"],
            "items": payload_items,
        },
        headers=auth_headers,
    )
    assert log_res.status_code == 201

    # Step 3: Refresh recommendation -> breakfast is no longer recommended!
    res2 = client.get("/recommendations/today", headers=auth_headers)
    assert res2.status_code == 200
    data2 = res2.json()
    if data2["has_recommendation"]:
        if data2["type"] == "meal":
            assert data2["meal_type"] != "breakfast"
        else:
            assert data2["type"] == "exercise"
