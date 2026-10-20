import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from src.database import get_session
from src.main import app
from src.models import FoodItem
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


def _headers(client, username):
    res = client.post(
        "/auth/register",
        json={
            "username": username,
            "password": "StrongPassword123!",
            "weight": 70.0,
            "height": 175.0,
            "birthdate": "1995-05-15",
        },
    )
    assert res.status_code == 201
    res = client.post(
        "/auth/login",
        json={"username": username, "password": "StrongPassword123!"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def user_a(client):
    return _headers(client, "owner_a")


@pytest.fixture
def user_b(client):
    return _headers(client, "intruder_b")


@pytest.fixture
def a_data(client, user_a):
    with Session(engine) as session:
        food = FoodItem(
            name="Oatmeal",
            usda_fdc_id=777777,
            calories_per_100g=389.0,
            protein_per_100g=16.9,
            carbs_per_100g=66.3,
            fat_per_100g=6.9,
            base_unit="g",
        )
        session.add(food)
        session.commit()
        session.refresh(food)
        food_id = food.id

    meal = client.post(
        "/meals",
        headers=user_a,
        json={
            "date": "2026-09-01",
            "items": [{"food_id": food_id, "quantity": 50.0, "unit": "g"}],
        },
    )
    assert meal.status_code == 201

    exercise = client.post(
        "/exercises",
        headers=user_a,
        json={"date": "2026-09-01", "name": "Running", "duration_minutes": 30},
    )
    assert exercise.status_code == 201

    habit = client.post("/habits", headers=user_a, json={"name": "Stretch"})
    assert habit.status_code == 201
    habit_id = habit.json()["id"]

    log = client.post(
        f"/habits/{habit_id}/logs",
        headers=user_a,
        json={"date": "2026-09-01", "completed": True},
    )
    assert log.status_code in (200, 201)

    weight = client.post(
        "/weight", headers=user_a, json={"date": "2026-09-01", "weight": 69.0}
    )
    assert weight.status_code == 201

    return {
        "meal_id": meal.json()["id"],
        "exercise_id": exercise.json()["id"],
        "habit_id": habit_id,
    }


def test_user_b_cannot_access_user_a_meal(client, user_b, a_data):
    mid = a_data["meal_id"]
    assert client.get(f"/meals/{mid}", headers=user_b).status_code == 404
    assert (
        client.patch(
            f"/meals/{mid}/calories",
            headers=user_b,
            json={"override_calories": 1.0},
        ).status_code
        == 404
    )
    assert client.delete(f"/meals/{mid}", headers=user_b).status_code == 404


def test_user_b_cannot_access_user_a_exercise(client, user_b, a_data):
    eid = a_data["exercise_id"]
    assert client.get(f"/exercises/{eid}", headers=user_b).status_code == 404
    assert client.delete(f"/exercises/{eid}", headers=user_b).status_code == 404


def test_user_b_cannot_access_user_a_habit(client, user_b, a_data):
    hid = a_data["habit_id"]
    assert client.get(f"/habits/{hid}", headers=user_b).status_code == 404
    assert (
        client.patch(
            f"/habits/{hid}", headers=user_b, json={"name": "Hijacked"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/habits/{hid}/logs",
            headers=user_b,
            json={"date": "2026-09-02", "completed": True},
        ).status_code
        == 404
    )
    assert client.get(f"/habits/{hid}/logs", headers=user_b).status_code == 404
    assert (
        client.delete(f"/habits/{hid}/logs/2026-09-01", headers=user_b).status_code
        == 404
    )
    assert client.delete(f"/habits/{hid}", headers=user_b).status_code == 404


def test_user_b_lists_do_not_leak_user_a_records(client, user_b, a_data):
    assert client.get("/meals", headers=user_b).json() == []
    assert client.get("/exercises", headers=user_b).json() == []
    assert client.get("/habits", headers=user_b).json() == []
    weights = client.get("/weight", headers=user_b).json()
    assert all(w["weight"] != 69.0 for w in weights)


def test_user_a_data_survives_user_b_attempts(client, user_a, user_b, a_data):
    client.delete(f"/meals/{a_data['meal_id']}", headers=user_b)
    client.delete(f"/exercises/{a_data['exercise_id']}", headers=user_b)
    client.delete(f"/habits/{a_data['habit_id']}", headers=user_b)
    assert client.get(f"/meals/{a_data['meal_id']}", headers=user_a).status_code == 200
    assert (
        client.get(f"/exercises/{a_data['exercise_id']}", headers=user_a).status_code
        == 200
    )
    assert client.get(f"/habits/{a_data['habit_id']}", headers=user_a).status_code == 200
