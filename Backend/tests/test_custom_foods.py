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


# ── Q2: custom food endpoints ────────────────────────


def test_create_custom_food_serving_basis(client, user_a):
    res = client.post(
        "/foods/custom",
        json={
            "name": "  Jollof Rice  ",
            "basis": "serving",
            "serving_grams": 150,
            "serving_name": "plate",
            "calories": 300,
            "protein": 6,
            "carbs": 45,
            "fat": 9,
        },
        headers=user_a,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Jollof Rice"
    assert body["kind"] == "custom"
    assert pytest.approx(body["calories_per_100g"], rel=1e-3) == 200.0
    assert pytest.approx(body["protein_per_100g"], rel=1e-3) == 4.0
    assert pytest.approx(body["carbs_per_100g"], rel=1e-3) == 30.0
    assert pytest.approx(body["fat_per_100g"], rel=1e-3) == 6.0
    assert len(body["portions"]) == 1
    assert body["portions"][0]["name"] == "1 plate"
    assert body["portions"][0]["gram_weight"] == 150.0


def test_create_custom_food_per_100g_basis(client, user_a):
    res = client.post(
        "/foods/custom",
        json={
            "name": "Garri",
            "basis": "per_100g",
            "calories": 350,
            "protein": 2,
            "carbs": 84,
            "fat": 1,
        },
        headers=user_a,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["calories_per_100g"] == 350.0
    assert body["carbs_per_100g"] == 84.0
    assert body["portions"] == []


def test_custom_food_density_validation(client, user_a):
    res_cal = client.post(
        "/foods/custom",
        json={"name": "Too Dense", "basis": "per_100g", "calories": 950},
        headers=user_a,
    )
    assert res_cal.status_code == 422

    res_mac = client.post(
        "/foods/custom",
        json={
            "name": "Impossible Macros",
            "basis": "per_100g",
            "calories": 400,
            "protein": 50,
            "carbs": 40,
            "fat": 20,
        },
        headers=user_a,
    )
    assert res_mac.status_code == 422


def test_custom_food_duplicate_name_per_user(client, user_a, user_b):
    payload = {"name": "My Oats", "basis": "per_100g", "calories": 370}
    assert client.post("/foods/custom", json=payload, headers=user_a).status_code == 201
    assert (
        client.post(
            "/foods/custom",
            json={"name": "my oats", "basis": "per_100g", "calories": 360},
            headers=user_a,
        ).status_code
        == 409
    )
    assert client.post("/foods/custom", json=payload, headers=user_b).status_code == 201


def test_custom_food_update_and_delete_and_logged_meal_survival(client, user_a, user_b):
    created = client.post(
        "/foods/custom",
        json={
            "name": "Plantain",
            "basis": "serving",
            "serving_grams": 100,
            "calories": 120,
            "carbs": 30,
        },
        headers=user_a,
    ).json()
    food_id = created["id"]

    # Other user cannot PATCH or DELETE
    assert (
        client.patch(
            f"/foods/custom/{food_id}",
            json={"calories": 150},
            headers=user_b,
        ).status_code
        == 404
    )
    assert client.delete(f"/foods/custom/{food_id}", headers=user_b).status_code == 404

    # Owner updates serving_grams and calories
    patched = client.patch(
        f"/foods/custom/{food_id}",
        json={"basis": "serving", "serving_grams": 200, "calories": 300},
        headers=user_a,
    )
    assert patched.status_code == 200
    assert pytest.approx(patched.json()["calories_per_100g"], rel=1e-3) == 150.0
    assert patched.json()["portions"][0]["gram_weight"] == 200.0

    # Log a meal before deleting the food
    meal_res = _meal(client, user_a, {"food_id": food_id, "quantity": 100, "unit": "g"})
    assert meal_res.status_code == 201
    meal_id = meal_res.json()["id"]

    # Delete food
    del_res = client.delete(f"/foods/custom/{food_id}", headers=user_a)
    assert del_res.status_code in (200, 204)

    # Disappears from list and search
    assert food_id not in _food_ids(client.get("/foods", headers=user_a))
    assert food_id not in _food_ids(
        client.get("/foods/search", params={"q": "Plantain"}, headers=user_a)
    )

    # Logged meal still displays food name and nutrition
    meals = client.get("/meals", headers=user_a).json()
    logged = next(m for m in meals if m["id"] == meal_id)
    assert logged["items"][0]["food_name"] == "Plantain"
    assert logged["calories"] == 150.0


# ── Q3: personal portions ────────────────────────────


def test_personal_portion_endpoints(client, user_a, user_b):
    food_id = _add_food(name="White Rice", calories_per_100g=130.0)

    # Create personal portion
    res = client.post(
        f"/foods/{food_id}/portions",
        json={"name": "my plate of rice", "grams": 240},
        headers=user_a,
    )
    assert res.status_code == 201
    portion = res.json()
    portion_id = portion["id"]
    assert portion["name"] == "my plate of rice"
    assert portion["gram_weight"] == 240.0
    assert portion["quantity"] == 1.0
    assert portion["unit"] == "portion"

    # Duplicate name for same food and user -> 409
    dup = client.post(
        f"/foods/{food_id}/portions",
        json={"name": "My Plate Of Rice", "grams": 200},
        headers=user_a,
    )
    assert dup.status_code == 409

    # Other user doesn't see it
    b_food = client.get(f"/foods/{food_id}", headers=user_b).json()
    assert portion_id not in {p["id"] for p in b_food["portions"]}

    # Logging 1.5x with it resolves quantity * grams = 360g -> 468 kcal
    meal_a = _meal(
        client,
        user_a,
        {"food_id": food_id, "quantity": 1.5, "portion_id": portion_id},
    )
    assert meal_a.status_code == 201
    assert meal_a.json()["items"][0]["gram_weight"] == 360.0
    assert pytest.approx(meal_a.json()["calories"], rel=1e-3) == 468.0

    # Another user logging with its id gets 400
    meal_b = _meal(
        client,
        user_b,
        {"food_id": food_id, "quantity": 1, "portion_id": portion_id},
    )
    assert meal_b.status_code == 400

    # Delete ownership: user_b gets 404, user_a deletes it
    assert client.delete(f"/foods/portions/{portion_id}", headers=user_b).status_code == 404
    del_res = client.delete(f"/foods/portions/{portion_id}", headers=user_a)
    assert del_res.status_code in (200, 204)
    a_food = client.get(f"/foods/{food_id}", headers=user_a).json()
    assert portion_id not in {p["id"] for p in a_food["portions"]}

