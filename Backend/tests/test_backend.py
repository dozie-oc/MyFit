# tests/test_backend.py

"""
Comprehensive backend tests for the fitness tracker.

Run with:

    pytest -v

Run with more detailed output:

    pytest -v -s

These tests intentionally use a temporary SQLite database instead
of the application's real database.

USDA API calls are mocked so tests do not depend on:
    - an internet connection
    - USDA availability
    - USDA rate limits
    - a real USDA API key
"""


# ============================================================
# IMPORTS
# ============================================================

from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from src.auth.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from src.config import settings
from src.database import get_session
from src.main import app
from src.models import FoodItem, FoodPortion, User
from src.services.food_service import (
    CARBOHYDRATE_NUTRIENT_ID,
    ENERGY_NUTRIENT_ID,
    FAT_NUTRIENT_ID,
    PROTEIN_NUTRIENT_ID,
    FoodService,
    NormalizedNutrients,
)
from tests.conftest import make_test_engine


# ============================================================
# TEST DATABASE
# ============================================================

engine = make_test_engine()


# ============================================================
# DATABASE DEPENDENCY OVERRIDE
# ============================================================


def get_test_session():
    with Session(engine) as session:
        yield session


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture(autouse=True)
def clean_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def client():
    """
    Create a FastAPI test client.
    """
    app.dependency_overrides[get_session] = get_test_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def session():
    """
    Provide a test database session.
    """
    app.dependency_overrides[get_session] = get_test_session

    with Session(engine) as test_session:
        yield test_session


@pytest.fixture
def registered_user(client):
    """
    Register and return a test user.
    """

    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "password": "StrongPassword123!",
            "weight": 70.0,
            "height": 175.0,
            "birthdate": "2000-01-01",
        },
    )

    assert response.status_code == 201

    return response.json()


@pytest.fixture
def auth_headers(client, registered_user):
    """
    Login and return Authorization headers.
    """

    response = client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture
def food(session):
    """
    Create a local food directly in the test database.
    """

    food = FoodItem(
        name="Test Banana",
        usda_fdc_id=999999,
        usda_data_type="Foundation",
        calories_per_100g=89.0,
        protein_per_100g=1.1,
        carbs_per_100g=22.8,
        fat_per_100g=0.3,
        base_unit="g",
    )

    session.add(food)
    session.commit()
    session.refresh(food)

    return food


@pytest.fixture
def food_with_portion(session, food):
    """
    Add a portion to the test food.
    """

    portion = FoodPortion(
        food_id=food.id,
        name="1 medium banana",
        quantity=1,
        unit="medium",
        gram_weight=118.0,
        usda_measure_unit="medium",
    )

    session.add(portion)
    session.commit()
    session.refresh(portion)

    return food, portion


# ============================================================
# AUTHENTICATION TESTS
# ============================================================


def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "alice",
            "password": "StrongPassword123!",
            "weight": 70.0,
            "height": 175.0,
            "birthdate": "2000-01-01",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["username"] == "alice"
    assert data["weight"] == 70.0
    assert data["height"] == 175.0
    assert data["birthdate"] == "2000-01-01"
    assert "id" in data
    assert "age" in data


def test_password_is_not_returned(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "alice",
            "password": "StrongPassword123!",
            "weight": 70.0,
            "height": 175.0,
            "birthdate": "2000-01-01",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert "password" not in data
    assert "hashed_password" not in data


def test_duplicate_username_is_rejected(
    client,
    registered_user,
):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "password": "AnotherPassword123!",
            "weight": 75.0,
            "height": 180.0,
            "birthdate": "1999-01-01",
        },
    )

    assert response.status_code == 409


def test_login_success(
    client,
    registered_user,
):
    response = client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_login_wrong_password(
    client,
    registered_user,
):
    response = client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "WrongPassword!",
        },
    )

    assert response.status_code == 401


def test_login_nonexistent_user(client):
    response = client.post(
        "/auth/login",
        json={
            "username": "doesnotexist",
            "password": "WrongPassword!",
        },
    )

    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user(
    client,
    auth_headers,
):
    response = client.get(
        "/auth/me",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["username"] == "testuser"
    assert data["weight"] == 70.0
    assert data["height"] == 175.0
    assert "age" in data


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer invalid.token.here",
        },
    )

    assert response.status_code == 401


def test_malformed_authorization_header(client):
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "NotBearer token",
        },
    )

    assert response.status_code == 401


# ============================================================
# LOCAL FOOD TESTS
# ============================================================


def test_get_foods_requires_auth(client):
    response = client.get("/foods")

    assert response.status_code == 401


def test_get_foods(
    client,
    auth_headers,
    food,
):
    response = client.get(
        "/foods",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 1

    returned_food = next(
        item
        for item in data
        if item["id"] == food.id
    )

    assert returned_food["name"] == "Test Banana"
    assert returned_food["calories_per_100g"] == 89.0


def test_get_single_food(
    client,
    auth_headers,
    food,
):
    response = client.get(
        f"/foods/{food.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == food.id
    assert data["name"] == "Test Banana"


def test_get_nonexistent_food(
    client,
    auth_headers,
):
    response = client.get(
        "/foods/999999",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_local_food_search(
    client,
    auth_headers,
    food,
):
    response = client.get(
        "/foods/search",
        params={
            "q": "banana",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert any(
        item["id"] == food.id
        for item in data
    )


def test_local_food_search_is_case_insensitive(
    client,
    auth_headers,
    food,
):
    response = client.get(
        "/foods/search",
        params={
            "q": "BANANA",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert any(
        item["id"] == food.id
        for item in data
    )


def test_local_food_search_empty_query(
    client,
    auth_headers,
):
    response = client.get(
        "/foods/search",
        params={
            "q": "   ",
        },
        headers=auth_headers,
    )

    assert response.status_code in {
        400,
        422,
    }


# ============================================================
# FOOD PORTION TESTS
# ============================================================


def test_food_returns_portions(
    client,
    auth_headers,
    food_with_portion,
):
    food, portion = food_with_portion

    response = client.get(
        f"/foods/{food.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert "portions" in data
    assert len(data["portions"]) == 1

    returned_portion = data["portions"][0]

    assert returned_portion["id"] == portion.id
    assert returned_portion["name"] == "1 medium banana"
    assert returned_portion["quantity"] == 1
    assert returned_portion["gram_weight"] == 118.0


# ============================================================
# FOOD SERVICE UNIT TESTS
# ============================================================


def test_extract_nutrients():
    food_data = {
        "foodNutrients": [
            {
                "nutrientId": 1008,
                "value": 89,
            },
            {
                "nutrientId": 1003,
                "value": 1.1,
            },
            {
                "nutrientId": 1004,
                "value": 0.3,
            },
            {
                "nutrientId": 1005,
                "value": 22.8,
            },
        ]
    }

    nutrients = FoodService._extract_nutrients(
        food_data
    )

    assert isinstance(
        nutrients,
        NormalizedNutrients,
    )

    assert nutrients.calories_per_100g == 89.0
    assert nutrients.protein_per_100g == 1.1
    assert nutrients.fat_per_100g == 0.3
    assert nutrients.carbs_per_100g == 22.8


def test_missing_nutrients_default_to_zero():
    food_data = {
        "foodNutrients": [
            {
                "nutrientId": 1008,
                "value": 89,
            }
        ]
    }

    nutrients = FoodService._extract_nutrients(
        food_data
    )

    assert nutrients.calories_per_100g == 89.0
    assert nutrients.protein_per_100g == 0.0
    assert nutrients.carbs_per_100g == 0.0
    assert nutrients.fat_per_100g == 0.0


def test_normalize_usda_food():
    food_data = {
        "fdcId": 12345,
        "description": "Bananas, raw",
        "dataType": "Foundation",
        "foodNutrients": [
            {
                "nutrientId": 1008,
                "value": 89,
            },
            {
                "nutrientId": 1003,
                "value": 1.1,
            },
            {
                "nutrientId": 1004,
                "value": 0.3,
            },
            {
                "nutrientId": 1005,
                "value": 22.8,
            },
        ],
        "foodPortions": [
            {
                "amount": 1,
                "modifier": "medium",
                "gramWeight": 118,
                "measureUnit": {
                    "name": "banana",
                    "abbreviation": "banana",
                },
            }
        ],
    }

    normalized = FoodService.normalize_usda_food(
        food_data
    )

    assert normalized.usda_fdc_id == 12345
    assert normalized.name == "Bananas, raw"
    assert normalized.usda_data_type == "Foundation"

    assert normalized.nutrients.calories_per_100g == 89
    assert normalized.nutrients.protein_per_100g == 1.1
    assert normalized.nutrients.carbs_per_100g == 22.8
    assert normalized.nutrients.fat_per_100g == 0.3

    assert len(normalized.portions) == 1
    assert normalized.portions[0].gram_weight == 118


def test_normalize_usda_food_requires_fdc_id():
    with pytest.raises(ValueError):
        FoodService.normalize_usda_food(
            {
                "description": "Banana",
            }
        )


def test_normalize_usda_food_requires_description():
    with pytest.raises(ValueError):
        FoodService.normalize_usda_food(
            {
                "fdcId": 123,
            }
        )


# ============================================================
# NUTRITION CALCULATION TESTS
# ============================================================


def test_calculate_nutrition_from_100g(food):
    result = FoodService.calculate_nutrition_from_grams(
        food,
        100,
    )

    assert result["calories"] == 89.0
    assert result["protein"] == 1.1
    assert result["carbs"] == 22.8
    assert result["fat"] == 0.3


def test_calculate_nutrition_from_200g(food):
    result = FoodService.calculate_nutrition_from_grams(
        food,
        200,
    )

    assert result["calories"] == 178.0
    assert result["protein"] == 2.2
    assert result["carbs"] == 45.6
    assert result["fat"] == 0.6


def test_calculate_nutrition_from_50g(food):
    result = FoodService.calculate_nutrition_from_grams(
        food,
        50,
    )

    assert result["calories"] == 44.5
    assert result["protein"] == 0.55
    assert result["carbs"] == 11.4
    assert result["fat"] == 0.15


def test_calculate_nutrition_rejects_zero(food):
    with pytest.raises(ValueError):
        FoodService.calculate_nutrition_from_grams(
            food,
            0,
        )


def test_calculate_nutrition_rejects_negative(food):
    with pytest.raises(ValueError):
        FoodService.calculate_nutrition_from_grams(
            food,
            -10,
        )


# ============================================================
# GRAM WEIGHT TESTS
# ============================================================


def test_calculate_gram_weight_direct_grams():
    result = FoodService.calculate_gram_weight(
        quantity=150,
        unit="g",
    )

    assert result == 150


def test_calculate_gram_weight_gram_aliases():
    assert (
        FoodService.calculate_gram_weight(
            quantity=150,
            unit="gram",
        )
        == 150
    )

    assert (
        FoodService.calculate_gram_weight(
            quantity=150,
            unit="grams",
        )
        == 150
    )


def test_calculate_gram_weight_from_portion(
    food_with_portion,
):
    _, portion = food_with_portion

    result = FoodService.calculate_gram_weight(
        quantity=2,
        portion=portion,
    )

    assert result == 236.0


def test_calculate_gram_weight_fractional_portion(
    food_with_portion,
):
    _, portion = food_with_portion

    result = FoodService.calculate_gram_weight(
        quantity=0.5,
        portion=portion,
    )

    assert result == 59.0


def test_calculate_gram_weight_requires_positive_quantity():
    with pytest.raises(ValueError):
        FoodService.calculate_gram_weight(
            quantity=0,
            unit="g",
        )

    with pytest.raises(ValueError):
        FoodService.calculate_gram_weight(
            quantity=-5,
            unit="g",
        )


def test_calculate_gram_weight_requires_unit():
    with pytest.raises(ValueError):
        FoodService.calculate_gram_weight(
            quantity=100,
        )


def test_calculate_gram_weight_rejects_unsupported_unit():
    with pytest.raises(ValueError):
        FoodService.calculate_gram_weight(
            quantity=2,
            unit="cups",
        )


# ============================================================
# PORTION OWNERSHIP TESTS
# ============================================================


def test_portion_belongs_to_food(
    session,
    food_with_portion,
):
    food, portion = food_with_portion

    service = FoodService(
        session=session,
        usda_client=None,
    )

    result = service.get_food_portion_for_food(
        food_id=food.id,
        portion_id=portion.id,
    )

    assert result is not None
    assert result.id == portion.id


def test_portion_cannot_be_used_with_wrong_food(
    session,
    food_with_portion,
):
    food, portion = food_with_portion

    second_food = FoodItem(
        name="Second Food",
        usda_fdc_id=888888,
        usda_data_type="Foundation",
        calories_per_100g=100,
        protein_per_100g=5,
        carbs_per_100g=10,
        fat_per_100g=2,
        base_unit="g",
    )

    session.add(second_food)
    session.commit()
    session.refresh(second_food)

    service = FoodService(
        session=session,
        usda_client=None,
    )

    result = service.get_food_portion_for_food(
        food_id=second_food.id,
        portion_id=portion.id,
    )

    assert result is None


def test_resolve_gram_weight_with_portion(
    session,
    food_with_portion,
):
    food, portion = food_with_portion

    service = FoodService(
        session=session,
        usda_client=None,
    )

    result = service.resolve_gram_weight(
        food_id=food.id,
        quantity=2,
        portion_id=portion.id,
        unit=None,
    )

    assert result == 236.0


def test_resolve_gram_weight_with_grams(
    session,
    food,
):
    service = FoodService(
        session=session,
        usda_client=None,
    )

    result = service.resolve_gram_weight(
        food_id=food.id,
        quantity=150,
        portion_id=None,
        unit="g",
    )

    assert result == 150


# ============================================================
# SOFT DELETE TESTS
# ============================================================


def test_deleted_food_is_not_returned(
    client,
    auth_headers,
    session,
):
    food = FoodItem(
        name="Deleted Food",
        usda_fdc_id=777777,
        usda_data_type="Foundation",
        calories_per_100g=100,
        protein_per_100g=5,
        carbs_per_100g=10,
        fat_per_100g=2,
        base_unit="g",
    )

    session.add(food)
    session.commit()
    session.refresh(food)

    food.deleted_at = datetime.now(timezone.utc)

    session.add(food)
    session.commit()

    response = client.get(
        f"/foods/{food.id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_deleted_user_cannot_login(
    client,
    session,
):
    user = User(
        username="deleteduser",
        hashed_password=hash_password(
            "StrongPassword123!"
        ),
        weight=70,
        height=175,
        birthdate=date(2000, 1, 1),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    user.deleted_at = datetime.now(timezone.utc)

    session.add(user)
    session.commit()

    response = client.post(
        "/auth/login",
        json={
            "username": "deleteduser",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 401


# ============================================================
# USDA MOCK DATA
# ============================================================


MOCK_USDA_SEARCH_RESPONSE = {
    "foods": [
        {
            "fdcId": 1001,
            "description": "Bananas, raw",
            "dataType": "Foundation",
        },
        {
            "fdcId": 1002,
            "description": "Banana chips",
            "dataType": "Branded",
        },
    ],
    "totalHits": 2,
}


MOCK_USDA_FOOD_RESPONSE = {
    "fdcId": 1001,
    "description": "Bananas, raw",
    "dataType": "Foundation",
    "foodNutrients": [
        {
            "nutrientId": 1008,
            "value": 89,
        },
        {
            "nutrientId": 1003,
            "value": 1.1,
        },
        {
            "nutrientId": 1004,
            "value": 0.3,
        },
        {
            "nutrientId": 1005,
            "value": 22.8,
        },
    ],
    "foodPortions": [
        {
            "amount": 1,
            "modifier": "medium",
            "gramWeight": 118,
            "measureUnit": {
                "name": "banana",
                "abbreviation": "banana",
            },
        },
    ],
}


# ============================================================
# USDA SERVICE TESTS
# ============================================================


class FakeUSDAClient:
    """
    Fake USDA client used to test FoodService without HTTP.
    """

    async def search_foods(
        self,
        query,
        *,
        page_size=25,
        page_number=1,
        data_types=None,
    ):
        return MOCK_USDA_SEARCH_RESPONSE

    async def get_food(
        self,
        fdc_id,
    ):
        return MOCK_USDA_FOOD_RESPONSE


@pytest.mark.asyncio
async def test_usda_search_service():
    service = FoodService(
        session=None,
        usda_client=FakeUSDAClient(),
    )

    results, total_hits = await service.search_foods(
        "banana"
    )

    assert total_hits == 2
    assert len(results) == 2

    assert results[0].fdc_id == 1001
    assert results[0].name == "Bananas, raw"
    assert results[0].data_type == "Foundation"


@pytest.mark.asyncio
async def test_usda_search_rejects_empty_query():
    service = FoodService(
        session=None,
        usda_client=FakeUSDAClient(),
    )

    with pytest.raises(ValueError):
        await service.search_foods("   ")


@pytest.mark.asyncio
async def test_usda_search_rejects_invalid_page_size():
    service = FoodService(
        session=None,
        usda_client=FakeUSDAClient(),
    )

    with pytest.raises(ValueError):
        await service.search_foods(
            "banana",
            page_size=0,
        )

    with pytest.raises(ValueError):
        await service.search_foods(
            "banana",
            page_size=51,
        )


@pytest.mark.asyncio
async def test_usda_search_rejects_invalid_page_number():
    service = FoodService(
        session=None,
        usda_client=FakeUSDAClient(),
    )

    with pytest.raises(ValueError):
        await service.search_foods(
            "banana",
            page_number=0,
        )


# ============================================================
# USDA IMPORT TESTS
# ============================================================


@pytest.mark.asyncio
async def test_import_usda_food(session):
    service = FoodService(
        session=session,
        usda_client=FakeUSDAClient(),
    )

    food = await service.import_usda_food(1001)

    session.commit()
    session.refresh(food)

    assert food.name == "Bananas, raw"
    assert food.usda_fdc_id == 1001
    assert food.usda_data_type == "Foundation"

    assert food.calories_per_100g == 89
    assert food.protein_per_100g == 1.1
    assert food.carbs_per_100g == 22.8
    assert food.fat_per_100g == 0.3
    assert food.base_unit == "g"

    portions = session.exec(
        select(FoodPortion).where(
            FoodPortion.food_id == food.id
        )
    ).all()

    assert len(portions) == 1
    assert portions[0].gram_weight == 118


@pytest.mark.asyncio
async def test_import_same_usda_food_does_not_duplicate(
    session,
):
    service = FoodService(
        session=session,
        usda_client=FakeUSDAClient(),
    )

    first_food = await service.import_usda_food(1001)

    session.commit()

    second_food = await service.import_usda_food(1001)

    session.commit()

    assert first_food.id == second_food.id

    foods = session.exec(
        select(FoodItem).where(
            FoodItem.usda_fdc_id == 1001
        )
    ).all()

    assert len(foods) == 1


@pytest.mark.asyncio
async def test_import_invalid_fdc_id(session):
    service = FoodService(
        session=session,
        usda_client=FakeUSDAClient(),
    )

    with pytest.raises(ValueError):
        await service.import_usda_food(0)

    with pytest.raises(ValueError):
        await service.import_usda_food(-1)


# ============================================================
# USDA API ENDPOINT TESTS
# ============================================================


def test_usda_search_requires_auth(client):
    response = client.get(
        "/foods/usda/search",
        params={
            "q": "banana",
        },
    )

    assert response.status_code == 401


def test_usda_search_endpoint(
    client,
    auth_headers,
    monkeypatch,
):
    """
    Replace USDAClient with a fake client so the endpoint can
    be tested without making a real HTTP request.
    """

    class FakeClient:
        def __init__(self, settings):
            pass

        async def __aenter__(self):
            return FakeUSDAClient()

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

    monkeypatch.setattr(
        "src.routers.foods.USDAClient",
        FakeClient,
    )

    response = client.get(
        "/foods/usda/search",
        params={
            "q": "banana",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["fdc_id"] == 1001


def test_usda_search_query_validation(
    client,
    auth_headers,
):
    response = client.get(
        "/foods/usda/search",
        params={
            "q": "a",
        },
        headers=auth_headers,
    )

    assert response.status_code == 422


# ============================================================
# USDA IMPORT ENDPOINT
# ============================================================


def test_usda_import_endpoint(
    client,
    auth_headers,
    monkeypatch,
):
    class FakeClient:
        def __init__(self, settings):
            pass

        async def __aenter__(self):
            return FakeUSDAClient()

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):
            pass

    monkeypatch.setattr(
        "src.routers.foods.USDAClient",
        FakeClient,
    )

    response = client.post(
        "/foods/usda/1001/import",
        headers=auth_headers,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Bananas, raw"
    assert data["calories_per_100g"] == 89
    assert len(data["portions"]) == 1


def test_usda_import_invalid_id(
    client,
    auth_headers,
):
    response = client.post(
        "/foods/usda/0/import",
        headers=auth_headers,
    )

    assert response.status_code == 400


# ============================================================
# APPLICATION HEALTH / ROUTE SANITY
# ============================================================


def test_openapi_available(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200

    data = response.json()

    assert "openapi" in data
    assert "paths" in data


def test_docs_available(client):
    response = client.get("/docs")

    assert response.status_code == 200


# ============================================================
# CONFIGURATION TESTS
# ============================================================


def test_settings_load():
    assert settings.secret_key
    assert len(settings.secret_key) >= 32

    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes > 0

    assert settings.usda_base_url
    assert settings.usda_timeout_seconds > 0


# ============================================================
# PASSWORD & TOKEN UNIT TESTS
# ============================================================


def test_password_is_hashed():
    password = "MySecurePassword123!"

    hashed = hash_password(password)

    assert hashed != password
    assert isinstance(hashed, str)


def test_password_verification():
    password = "MySecurePassword123!"

    assert verify_password(password, hash_password(password))


def test_wrong_password_fails():
    hashed = hash_password("MySecurePassword123!")

    assert not verify_password("WrongPassword", hashed)


def test_different_passwords_have_different_hashes():
    password = "MySecurePassword123!"

    hash_one = hash_password(password)
    hash_two = hash_password(password)

    # Salted hashing: same input, different hashes, both verify.
    assert hash_one != hash_two
    assert verify_password(password, hash_one)
    assert verify_password(password, hash_two)


def test_expired_token_is_rejected(session, registered_user):
    expired_token = jwt.encode(
        {
            "sub": str(registered_user["id"]),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=expired_token, session=session)

    assert exc_info.value.status_code == 401


def test_invalid_token_rejected_by_dependency(session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token="this-is-not-a-valid-token", session=session)

    assert exc_info.value.status_code == 401


# ============================================================
# USDA NUTRIENT / PORTION EDGE CASES
# ============================================================


def test_invalid_nutrient_values_are_ignored():
    food_data = {
        "foodNutrients": [
            {"nutrientId": ENERGY_NUTRIENT_ID, "value": "invalid"},
            {"nutrientId": PROTEIN_NUTRIENT_ID, "value": None},
        ]
    }

    nutrients = FoodService._extract_nutrients(food_data)

    assert nutrients.calories_per_100g == 0
    assert nutrients.protein_per_100g == 0


def test_negative_nutrient_values_become_zero():
    food_data = {
        "foodNutrients": [
            {"nutrientId": ENERGY_NUTRIENT_ID, "value": -100},
        ]
    }

    nutrients = FoodService._extract_nutrients(food_data)

    assert nutrients.calories_per_100g == 0


def test_extract_portions():
    food_data = {
        "foodPortions": [
            {
                "amount": 1,
                "modifier": "large",
                "measureUnit": {"name": "egg", "abbreviation": "egg"},
                "gramWeight": 50,
            }
        ]
    }

    portions = FoodService._extract_portions(food_data)

    assert len(portions) == 1

    portion = portions[0]

    assert portion.quantity == 1
    assert portion.gram_weight == 50
    assert portion.unit == "egg"
    assert portion.name == "1 large egg"


def test_portions_without_gram_weight_are_ignored():
    food_data = {
        "foodPortions": [
            {
                "amount": 1,
                "modifier": "large",
                "measureUnit": {"name": "egg"},
                "gramWeight": None,
            }
        ]
    }

    assert FoodService._extract_portions(food_data) == []


def test_zero_gram_portions_are_ignored():
    food_data = {
        "foodPortions": [
            {
                "amount": 1,
                "measureUnit": {"name": "serving"},
                "gramWeight": 0,
            }
        ]
    }

    assert FoodService._extract_portions(food_data) == []


def test_duplicate_portions_are_removed():
    portion = {
        "amount": 1,
        "modifier": "large",
        "measureUnit": {"name": "egg"},
        "gramWeight": 50,
    }

    portions = FoodService._extract_portions(
        {"foodPortions": [dict(portion), dict(portion)]}
    )

    assert len(portions) == 1


def test_normalize_food_rejects_invalid_fdc_id():
    with pytest.raises(ValueError):
        FoodService.normalize_usda_food(
            {"fdcId": "invalid", "description": "Banana"}
        )


def test_normalize_usda_food_includes_all_nutrients():
    normalized = FoodService.normalize_usda_food(
        {
            "fdcId": 12345,
            "description": "Banana, raw",
            "dataType": "Foundation",
            "foodNutrients": [
                {"nutrientId": ENERGY_NUTRIENT_ID, "value": 89},
                {"nutrientId": PROTEIN_NUTRIENT_ID, "value": 1.1},
                {"nutrientId": CARBOHYDRATE_NUTRIENT_ID, "value": 22.8},
                {"nutrientId": FAT_NUTRIENT_ID, "value": 0.3},
            ],
            "foodPortions": [
                {
                    "amount": 1,
                    "modifier": "medium",
                    "measureUnit": {"name": "banana"},
                    "gramWeight": 118,
                }
            ],
        }
    )

    assert normalized.name == "Banana, raw"
    assert normalized.usda_fdc_id == 12345
    assert normalized.usda_data_type == "Foundation"
    assert normalized.nutrients.calories_per_100g == 89
    assert normalized.nutrients.carbs_per_100g == 22.8
    assert len(normalized.portions) == 1


def test_local_food_search_no_match(client, auth_headers, food):
    response = client.get(
        "/foods/search",
        params={"q": "chicken"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


# ============================================================
# CLEANUP
# ============================================================


def teardown_module():
    """
    Remove the test dependency override after the test module
    finishes.
    """

    app.dependency_overrides.clear()