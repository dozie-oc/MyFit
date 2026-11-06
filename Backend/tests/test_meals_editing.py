from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from src.auth.auth import create_access_token
from src.database import get_session
from src.main import app
from src.models import DailySummary, FoodItem, FoodPortion, User
from src.services.food_service import FoodService
from tests.conftest import make_test_engine

engine = make_test_engine()


def get_test_session():
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def clean_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u1 = User(id=1, username="mealuser", hashed_password="hashed_pw_dummy")
        session.add(u1)
        session.commit()
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id=1)
    return {"Authorization": f"Bearer {token}"}


def test_direct_unit_conversions_and_unsupported_units():
    assert FoodService.calculate_gram_weight(quantity=150, unit="g") == pytest.approx(150.0)
    assert FoodService.calculate_gram_weight(quantity=0.5, unit="kg") == pytest.approx(500.0)
    assert FoodService.calculate_gram_weight(quantity=2.0, unit="oz") == pytest.approx(56.699)
    assert FoodService.calculate_gram_weight(quantity=1.0, unit="lb") == pytest.approx(453.592)
    assert FoodService.calculate_gram_weight(quantity=250, unit="ml") == pytest.approx(250.0)

    with pytest.raises(ValueError, match="Unsupported direct food unit"):
        FoodService.calculate_gram_weight(quantity=1.0, unit="cups")


def test_update_meal_changes_food_portion_unit_removes_item_and_recalculates(
    client,
    auth_headers,
):
    with Session(engine) as session:
        chicken = FoodItem(
            name="Grilled Chicken",
            calories_per_100g=165.0,
            protein_per_100g=31.0,
            carbs_per_100g=0.0,
            fat_per_100g=3.6,
        )
        rice = FoodItem(
            name="Cooked Rice",
            calories_per_100g=130.0,
            protein_per_100g=2.7,
            carbs_per_100g=28.0,
            fat_per_100g=0.3,
        )
        salmon = FoodItem(
            name="Atlantic Salmon",
            calories_per_100g=208.0,
            protein_per_100g=20.0,
            carbs_per_100g=0.0,
            fat_per_100g=13.0,
        )
        session.add_all([chicken, rice, salmon])
        session.commit()
        session.refresh(chicken)
        session.refresh(rice)
        session.refresh(salmon)

        rice_cup = FoodPortion(
            food_id=rice.id,
            name="1 cup cooked",
            quantity=1.0,
            unit="cup",
            gram_weight=200.0,
        )
        rice_bowl = FoodPortion(
            food_id=rice.id,
            name="1 large bowl",
            quantity=1.0,
            unit="bowl",
            gram_weight=300.0,
        )
        session.add_all([rice_cup, rice_bowl])
        session.commit()
        session.refresh(rice_cup)
        session.refresh(rice_bowl)
        chicken_id = chicken.id
        rice_id = rice.id
        salmon_id = salmon.id
        rice_cup_id = rice_cup.id
        rice_bowl_id = rice_bowl.id

    # 1. Create initial meal: 100g chicken + 1 cup rice (200g)
    # Chicken: 165 kcal, 31P, 0C, 3.6F
    # Rice (200g): 260 kcal, 5.4P, 56C, 0.6F
    # Total: 425 kcal, 36.4P, 56.0C, 4.2F
    create_res = client.post(
        "/meals",
        headers=auth_headers,
        json={
            "date": "2026-04-10",
            "meal_type": "lunch",
            "items": [
                {"food_id": chicken_id, "quantity": 100, "unit": "g"},
                {"food_id": rice_id, "quantity": 1, "portion_id": rice_cup_id},
            ],
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    meal_id = created["id"]
    assert created["calories"] == pytest.approx(425.0)
    assert created["protein"] == pytest.approx(36.4)
    assert created["carbs"] == pytest.approx(56.0)
    assert created["fat"] == pytest.approx(4.2)
    assert len(created["items"]) == 2

    # 2. Change food (Chicken -> Salmon 150g) and change portion on Rice (1 cup -> 1 large bowl 300g)
    # Salmon (150g): 312 kcal, 30.0P, 0C, 19.5F
    # Rice (300g): 390 kcal, 8.1P, 84.0C, 0.9F
    # Total: 702 kcal, 38.1P, 84.0C, 20.4F
    update_res = client.put(
        f"/meals/{meal_id}",
        headers=auth_headers,
        json={
            "date": "2026-04-10",
            "meal_type": "dinner",
            "items": [
                {"food_id": salmon_id, "quantity": 150, "unit": "g"},
                {"food_id": rice_id, "quantity": 1, "portion_id": rice_bowl_id},
            ],
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["meal_type"] == "dinner"
    assert updated["calories"] == pytest.approx(702.0)
    assert updated["protein"] == pytest.approx(38.1)
    assert updated["carbs"] == pytest.approx(84.0)
    assert updated["fat"] == pytest.approx(20.4)
    assert [it["food_name"] for it in updated["items"]] == [
        "Atlantic Salmon",
        "Cooked Rice",
    ]

    # 3. Remove Rice item and change Salmon unit to 0.2 kg (200g)
    # Salmon (200g): 416 kcal, 40.0P, 0C, 26.0F
    remove_res = client.put(
        f"/meals/{meal_id}",
        headers=auth_headers,
        json={
            "items": [
                {"food_id": salmon_id, "quantity": 0.2, "unit": "kg"},
            ],
        },
    )
    assert remove_res.status_code == 200
    after_remove = remove_res.json()
    assert len(after_remove["items"]) == 1
    assert after_remove["items"][0]["gram_weight"] == pytest.approx(200.0)
    assert after_remove["calories"] == pytest.approx(416.0)
    assert after_remove["protein"] == pytest.approx(40.0)
    assert after_remove["carbs"] == pytest.approx(0.0)
    assert after_remove["fat"] == pytest.approx(26.0)

    # DailySummary is updated to match recalculated meal totals
    with Session(engine) as session:
        summary = session.exec(
            select(DailySummary).where(
                DailySummary.user_id == 1,
                DailySummary.date == date(2026, 4, 10),
            )
        ).first()
        assert summary is not None
        assert summary.calories_in == pytest.approx(416.0)
        assert summary.net_calories == pytest.approx(416.0)


def test_failed_meal_update_does_not_alter_existing_saved_meal(
    client,
    auth_headers,
):
    with Session(engine) as session:
        oats = FoodItem(
            name="Rolled Oats",
            calories_per_100g=389.0,
            protein_per_100g=16.9,
            carbs_per_100g=66.3,
            fat_per_100g=6.9,
        )
        session.add(oats)
        session.commit()
        session.refresh(oats)
        oats_id = oats.id

    create_res = client.post(
        "/meals",
        headers=auth_headers,
        json={
            "date": "2026-04-11",
            "meal_type": "breakfast",
            "items": [{"food_id": oats_id, "quantity": 100, "unit": "g"}],
        },
    )
    assert create_res.status_code == 201
    meal_id = create_res.json()["id"]

    # Attempt invalid update with unsupported unit
    bad_unit_res = client.put(
        f"/meals/{meal_id}",
        headers=auth_headers,
        json={
            "items": [{"food_id": oats_id, "quantity": 2, "unit": "cups"}],
        },
    )
    assert bad_unit_res.status_code == 400

    # Attempt invalid update with nonexistent food_id
    bad_food_res = client.put(
        f"/meals/{meal_id}",
        headers=auth_headers,
        json={
            "items": [{"food_id": 999999, "quantity": 100, "unit": "g"}],
        },
    )
    assert bad_food_res.status_code == 400

    # Verify saved meal is completely intact
    meals_res = client.get(
        "/meals",
        headers=auth_headers,
        params={"meal_date": "2026-04-11"},
    )
    assert meals_res.status_code == 200
    meals = meals_res.json()
    assert len(meals) == 1
    assert meals[0]["calories"] == pytest.approx(389.0)
    assert len(meals[0]["items"]) == 1
    assert meals[0]["items"][0]["food_id"] == oats_id
    assert meals[0]["items"][0]["gram_weight"] == pytest.approx(100.0)
