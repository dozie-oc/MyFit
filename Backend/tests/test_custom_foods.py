import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from src.database import get_session
from src.main import app
from src.models import FoodItem, FoodPortion
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
    return _headers(client, "cook_a")


@pytest.fixture
def user_b(client):
    return _headers(client, "cook_b")


def _user_id(client, headers):
    return client.get("/auth/me", headers=headers).json()["id"]


def _add_food(**kwargs):
    defaults = dict(
        calories_per_100g=100.0,
        protein_per_100g=5.0,
        carbs_per_100g=10.0,
        fat_per_100g=2.0,
    )
    defaults.update(kwargs)
    with Session(engine) as session:
        food = FoodItem(**defaults)
        session.add(food)
        session.commit()
        session.refresh(food)
        return food.id


def _add_portion(**kwargs):
    with Session(engine) as session:
        portion = FoodPortion(**kwargs)
        session.add(portion)
        session.commit()
        session.refresh(portion)
        return portion.id


def _meal(client, headers, item, date="2026-10-20"):
    return client.post(
        "/meals",
        json={"date": date, "meal_type": "lunch", "items": [item]},
        headers=headers,
    )


def _food_ids(res):
    assert res.status_code == 200
    return {f["id"] for f in res.json()}


# ── Q1: visibility scoping ───────────────────────────


def test_other_users_custom_food_is_hidden(client, user_a, user_b):
    a_id = _user_id(client, user_a)
    food_id = _add_food(name="Secret Stew", kind="custom", user_id=a_id)

    assert food_id in _food_ids(client.get("/foods", headers=user_a))
    assert food_id not in _food_ids(client.get("/foods", headers=user_b))
    assert food_id not in _food_ids(
        client.get("/foods/search", params={"q": "Secret"}, headers=user_b)
    )
    assert client.get(f"/foods/{food_id}", headers=user_b).status_code == 404
    assert client.get(f"/foods/{food_id}", headers=user_a).status_code == 200

    res = _meal(client, user_b, {"food_id": food_id, "quantity": 100, "unit": "g"})
    assert res.status_code == 400
    res = _meal(client, user_a, {"food_id": food_id, "quantity": 100, "unit": "g"})
    assert res.status_code == 201
    assert res.json()["items"][0]["food_kind"] == "custom"


def test_food_out_has_kind(client, user_a):
    food_id = _add_food(name="Plain Rice")
    res = client.get(f"/foods/{food_id}", headers=user_a)
    assert res.json()["kind"] == "catalog"


def test_personal_portion_is_private(client, user_a, user_b):
    a_id = _user_id(client, user_a)
    food_id = _add_food(name="Rice")
    portion_id = _add_portion(
        food_id=food_id, user_id=a_id, name="my plate",
        quantity=1, unit="portion", gram_weight=250,
    )

    a_portions = client.get(f"/foods/{food_id}", headers=user_a).json()["portions"]
    b_portions = client.get(f"/foods/{food_id}", headers=user_b).json()["portions"]
    assert portion_id in {p["id"] for p in a_portions}
    assert portion_id not in {p["id"] for p in b_portions}

    item = {"food_id": food_id, "quantity": 1, "portion_id": portion_id}
    assert _meal(client, user_b, item).status_code == 400
    res = _meal(client, user_a, item)
    assert res.status_code == 201
    assert res.json()["items"][0]["gram_weight"] == 250


def test_portion_of_another_food_rejected(client, user_a):
    food_id = _add_food(name="Rice")
    other_id = _add_food(name="Beans")
    portion_id = _add_portion(
        food_id=other_id, name="1 cup", quantity=1, unit="cup", gram_weight=170,
    )
    item = {"food_id": food_id, "quantity": 1, "portion_id": portion_id}
    assert _meal(client, user_a, item).status_code == 400


def test_quick_food_hidden_from_lists(client, user_a):
    a_id = _user_id(client, user_a)
    food_id = _add_food(name="Lunch estimate", kind="quick", user_id=a_id)
    assert food_id not in _food_ids(client.get("/foods", headers=user_a))
    assert food_id not in _food_ids(
        client.get("/foods/search", params={"q": "Lunch"}, headers=user_a)
    )


def test_recommendations_ignore_custom_foods(client, user_a):
    a_id = _user_id(client, user_a)
    _add_food(name="Zzcustom Pie", kind="custom", user_id=a_id,
              calories_per_100g=200, protein_per_100g=20)
    res = client.get(
        "/recommendations/today", params={"type": "meal"}, headers=user_a
    )
    assert res.status_code == 200
    names = [i.get("name", "") for i in res.json().get("items") or []]
    assert not any("Zzcustom" in n for n in names)

