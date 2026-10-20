from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from src.auth.auth import hash_password
from src.database import get_session
from src.config import settings
from src.main import app
from src.models import FoodItem, FoodPortion, User
from tests.conftest import make_test_engine

engine = make_test_engine()


def get_test_session():
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def clean_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def session():
    app.dependency_overrides[get_session] = get_test_session
    with Session(engine) as test_session:
        yield test_session


@pytest.fixture
def registered_user(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "featureuser",
            "password": "StrongPassword123!",
            "weight": 75.0,
            "height": 180.0,
            "birthdate": "1995-05-15",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(client, registered_user):
    response = client.post(
        "/auth/login",
        json={
            "username": "featureuser",
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_food(session):
    food = FoodItem(
        name="Oatmeal",
        usda_fdc_id=888888,
        calories_per_100g=389.0,
        protein_per_100g=16.9,
        carbs_per_100g=66.3,
        fat_per_100g=6.9,
        base_unit="g",
    )
    session.add(food)
    session.commit()
    session.refresh(food)

    portion = FoodPortion(
        food_id=food.id,
        name="1 cup cooked",
        quantity=1,
        unit="cup",
        gram_weight=234.0,
    )
    session.add(portion)
    session.commit()
    session.refresh(portion)
    return food, portion


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Fitness Tracker API is running"}


# ============================================================
# MEAL TESTS
# ============================================================


def test_create_and_get_meal(client, auth_headers, sample_food):
    food, portion = sample_food

    response = client.post(
        "/meals",
        headers=auth_headers,
        json={
            "date": "2026-09-01",
            "items": [
                {
                    "food_id": food.id,
                    "portion_id": portion.id,
                    "quantity": 1.0,
                },
                {
                    "food_id": food.id,
                    "quantity": 50.0,
                    "unit": "g",
                },
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["date"] == "2026-09-01"
    assert len(data["items"]) == 2
    assert data["calories"] > 0
    meal_id = data["id"]

    # Get meals
    get_res = client.get("/meals", headers=auth_headers)
    assert get_res.status_code == 200
    assert len(get_res.json()) == 1

    # Override calories
    patch_res = client.patch(
        f"/meals/{meal_id}/calories",
        headers=auth_headers,
        json={"override_calories": 500.0},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["calories"] == 500.0

    # Delete meal
    del_res = client.delete(f"/meals/{meal_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # Verify deleted
    get_del = client.get(f"/meals/{meal_id}", headers=auth_headers)
    assert get_del.status_code == 404


# ============================================================
# EXERCISE TESTS
# ============================================================


def test_exercise_lifecycle(client, auth_headers):
    response = client.post(
        "/exercises",
        headers=auth_headers,
        json={
            "date": "2026-09-01",
            "name": "Running",
            "duration_minutes": 30,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Running"
    assert data["calories_burned"] > 0
    exercise_id = data["id"]

    # Get single exercise
    get_res = client.get(f"/exercises/{exercise_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Running"

    # Strength exercise with sets, reps, weight
    strength_res = client.post(
        "/exercises",
        headers=auth_headers,
        json={
            "date": "2026-09-01",
            "name": "Bench Press",
            "category": "strength",
            "sets": 3,
            "reps": 10,
            "weight_kg": 60.0,
        },
    )
    assert strength_res.status_code == 201
    assert strength_res.json()["sets"] == 3
    assert strength_res.json()["calories_burned"] > 0

    # Exercise catalog
    cat_res = client.get("/exercises/catalog", headers=auth_headers)
    assert cat_res.status_code == 200
    assert isinstance(cat_res.json(), list)

    # Delete exercise
    del_res = client.delete(f"/exercises/{exercise_id}", headers=auth_headers)
    assert del_res.status_code == 204


# ============================================================
# WEIGHT & MEASUREMENTS TESTS
# ============================================================


def test_weight_logging(client, auth_headers):
    response = client.post(
        "/weight",
        headers=auth_headers,
        json={
            "date": "2026-09-01",
            "weight": 74.5,
        },
    )
    assert response.status_code == 201
    assert response.json()["weight"] == 74.5

    # Check that me endpoint reflects new weight
    me_res = client.get("/auth/me", headers=auth_headers)
    assert me_res.status_code == 200
    assert me_res.json()["weight"] == 74.5

    # Update measurements via patch
    patch_res = client.patch(
        "/auth/measurements",
        headers=auth_headers,
        json={
            "weight": 73.0,
            "height": 181.0,
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["weight"] == 73.0
    assert patch_res.json()["height"] == 181.0

    # List weight logs
    logs_res = client.get("/weight", headers=auth_headers)
    assert logs_res.status_code == 200
    assert len(logs_res.json()) >= 1


# ============================================================
# HABIT TESTS
# ============================================================


def test_habit_lifecycle(client, auth_headers):
    response = client.post(
        "/habits",
        headers=auth_headers,
        json={
            "name": "Drink Water",
            "description": "2L daily",
        },
    )
    assert response.status_code == 201
    habit_id = response.json()["id"]

    # Log completion
    log_res = client.post(
        f"/habits/{habit_id}/logs",
        headers=auth_headers,
        json={
            "date": "2026-09-01",
            "completed": True,
        },
    )
    assert log_res.status_code == 200
    assert log_res.json()["completed"] is True

    # Get habit logs
    logs_res = client.get(f"/habits/{habit_id}/logs", headers=auth_headers)
    assert logs_res.status_code == 200
    assert len(logs_res.json()) == 1

    # Delete habit
    del_res = client.delete(f"/habits/{habit_id}", headers=auth_headers)
    assert del_res.status_code == 204


# ============================================================
# DAILY SUMMARY TESTS
# ============================================================


def test_daily_summary_calculation(client, auth_headers, sample_food):
    food, portion = sample_food

    # Add meal
    client.post(
        "/meals",
        headers=auth_headers,
        json={
            "date": "2026-09-01",
            "items": [
                {
                    "food_id": food.id,
                    "portion_id": portion.id,
                    "quantity": 1.0,
                }
            ],
        },
    )

    # Add exercise
    client.post(
        "/exercises",
        headers=auth_headers,
        json={
            "date": "2026-09-01",
            "name": "Cycling",
            "duration_minutes": 20,
        },
    )

    # Get summary for date
    summary_res = client.get("/summary/2026-09-01", headers=auth_headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["date"] == "2026-09-01"
    assert summary["calories_in"] > 0
    assert summary["calories_out"] > 0
    assert summary["net_calories"] == summary["calories_in"] - summary["calories_out"]

    # Get all summaries
    all_res = client.get("/summary", headers=auth_headers)
    assert all_res.status_code == 200
    assert len(all_res.json()) >= 1


def test_admin_login_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_dev_admin", False)
    assert client.post("/auth/admin-login").status_code == 404


def test_admin_login_and_seeding(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_dev_admin", True)
    response = client.post("/auth/admin-login")
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token is not None

    headers = {"Authorization": f"Bearer {token}"}

    # Verify admin profile
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "admin"

    # Verify meals seeded
    meals_res = client.get("/meals", headers=headers)
    assert meals_res.status_code == 200
    assert len(meals_res.json()) >= 1

    # Verify exercises seeded
    ex_res = client.get("/exercises", headers=headers)
    assert ex_res.status_code == 200
    assert len(ex_res.json()) >= 1

    # Verify habits seeded
    habits_res = client.get("/habits", headers=headers)
    assert habits_res.status_code == 200
    assert len(habits_res.json()) == 4

    # Verify weight logs seeded
    weight_res = client.get("/weight", headers=headers)
    assert weight_res.status_code == 200
    assert len(weight_res.json()) >= 1

