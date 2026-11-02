from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from src.database import get_session, seed_exercise_catalog
from src.exercise_catalog_data import CATALOG, EQUIPMENT, LEVELS
from src.main import app
from src.models import ExerciseCatalogItem, ExerciseMuscleMapping
from src.services.training_service import ALL_MUSCLE_GROUPS
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
def session():
    with Session(engine) as sess:
        yield sess


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = get_test_session
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def _headers(client, username="catalog_user"):
    client.post(
        "/auth/register",
        json={
            "username": username,
            "password": "StrongPassword123!",
            "weight": 70.0,
            "height": 175.0,
            "birthdate": "1995-05-15",
        },
    )
    res = client.post(
        "/auth/login",
        json={"username": username, "password": "StrongPassword123!"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_seeding_idempotent_and_restores_deleted(session: Session):
    seed_exercise_catalog(session)
    items_1 = session.exec(select(ExerciseCatalogItem)).all()
    mappings_1 = session.exec(select(ExerciseMuscleMapping)).all()
    assert len(items_1) == len(CATALOG)
    assert len(mappings_1) > 0

    # Seeding a second time leaves identical row counts
    seed_exercise_catalog(session)
    items_2 = session.exec(select(ExerciseCatalogItem)).all()
    mappings_2 = session.exec(select(ExerciseMuscleMapping)).all()
    assert len(items_2) == len(items_1)
    assert len(mappings_2) == len(mappings_1)

    # Delete one standard row, reseed, it returns
    bench = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    assert bench is not None
    # Delete mappings for bench too or let reseed recreate
    for m in session.exec(
        select(ExerciseMuscleMapping).where(
            ExerciseMuscleMapping.exercise_catalog_id == bench.id
        )
    ).all():
        session.delete(m)
    session.delete(bench)
    session.commit()

    assert (
        session.exec(
            select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
        ).first()
        is None
    )

    seed_exercise_catalog(session)
    restored = session.exec(
        select(ExerciseCatalogItem).where(ExerciseCatalogItem.name == "Bench Press")
    ).first()
    assert restored is not None
    assert len(session.exec(select(ExerciseCatalogItem)).all()) == len(CATALOG)


def test_catalog_integrity_and_muscle_coverage(session: Session):
    seed_exercise_catalog(session)
    items = session.exec(select(ExerciseCatalogItem)).all()
    mappings = session.exec(select(ExerciseMuscleMapping)).all()

    # Names are unique case-insensitively
    lower_names = [i.name.lower() for i in items]
    assert len(lower_names) == len(set(lower_names))

    # Equipment tokens and levels are in the vocabulary
    vocab = set(EQUIPMENT)
    for item in items:
        tokens = item.equipment.split("|")
        assert all(t in vocab for t in tokens), f"Invalid equipment on {item.name}: {item.equipment}"
        assert item.level in LEVELS, f"Invalid level on {item.name}: {item.level}"

    # Group mappings by catalog_id
    by_item: dict[int, list[ExerciseMuscleMapping]] = {}
    for m in mappings:
        by_item.setdefault(m.exercise_catalog_id, []).append(m)

    # Every strength item has at least one primary mapping
    for item in items:
        if item.category == "strength":
            item_ms = by_item.get(item.id, [])
            primaries = [m for m in item_ms if m.role == "primary"]
            assert len(primaries) >= 1, f"{item.name} has no primary muscle mapping"

    # Each of the 11 groups in ALL_MUSCLE_GROUPS has at least 2 primary exercises (calves included)
    primary_counts = {g: 0 for g in ALL_MUSCLE_GROUPS}
    for m in mappings:
        if m.role == "primary" and m.muscle_group in primary_counts:
            primary_counts[m.muscle_group] += 1

    for group, count in primary_counts.items():
        assert count >= 2, f"Muscle group {group} only has {count} primary exercises"


def test_catalog_endpoint_returns_muscles(session: Session, client: TestClient):
    seed_exercise_catalog(session)
    headers = _headers(client)
    res = client.get("/exercises/catalog", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == len(CATALOG)

    by_name = {d["name"]: d for d in data}
    bench = by_name["Bench Press"]
    assert bench["equipment"] == "barbell"
    assert bench["level"] == "intermediate"
    assert len(bench["muscles"]) == 3
    primary_groups = {m["muscle_group"] for m in bench["muscles"] if m["role"] == "primary"}
    assert "chest" in primary_groups


def test_lowercase_logging_links_catalog_and_shows_in_adequacy(
    session: Session, client: TestClient
):
    seed_exercise_catalog(session)
    headers = _headers(client, "q2_user_a")
    res = client.post(
        "/exercises",
        headers=headers,
        json={
            "date": date.today().isoformat(),
            "name": "bench press",
            "category": "strength",
            "sets": 3,
            "reps": 8,
            "weight_kg": 60.0,
        },
    )
    assert res.status_code == 201
    ex_out = res.json()
    assert ex_out["exercise_catalog_id"] is not None

    # Adequacy reflects chest sets
    adeq = client.get("/exercises/adequacy", headers=headers)
    assert adeq.status_code == 200
    mg = {m["muscle_group"]: m for m in adeq.json()["muscle_groups"]}
    assert mg["chest"]["sets_completed"] == 3.0


def test_logging_other_users_custom_catalog_id_returns_400(
    session: Session, client: TestClient
):
    seed_exercise_catalog(session)
    headers_a = _headers(client, "q2_owner")
    headers_b = _headers(client, "q2_other")

    from src.models import User

    user_a = session.exec(select(User).where(User.username == "q2_owner")).first()
    custom_item = ExerciseCatalogItem(
        name="Secret A Press",
        category="strength",
        default_met=5.0,
        is_custom=True,
        user_id=user_a.id,
    )
    session.add(custom_item)
    session.commit()
    session.refresh(custom_item)

    res = client.post(
        "/exercises",
        headers=headers_b,
        json={
            "date": "2026-11-01",
            "name": "Secret A Press",
            "category": "strength",
            "exercise_catalog_id": custom_item.id,
            "sets": 3,
            "reps": 10,
        },
    )
    assert res.status_code == 400
    assert "Exercise not found in catalog" in res.json()["detail"]


@pytest.mark.parametrize(
    "item_equip,user_equip,expected",
    [
        ("barbell", set(), True),
        ("bodyweight", {"none"}, True),
        ("barbell", {"none"}, False),
        ("bodyweight", {"bodyweight"}, True),
        ("dumbbell", {"bodyweight"}, False),
        ("dumbbell", {"dumbbells"}, True),
        ("bodyweight", {"dumbbells"}, True),
        ("barbell", {"dumbbells"}, False),
        ("machines|cables", {"machine"}, True),
        ("machines|cables", {"cable"}, True),
        ("machines|cables", {"dumbbell"}, False),
        ("bands", {"bands"}, True),
        ("bands", {"band"}, True),
    ],
)
def test_equipment_ok_table(item_equip, user_equip, expected):
    from src.services.recommendation_service import _equipment_ok

    assert _equipment_ok(item_equip, user_equip) is expected


def test_recommender_scoping_variety_and_level(session: Session):
    from src.auth.auth import hash_password
    from src.models import Exercise, User, UserGoal
    from src.services.recommendation_service import get_recommendation

    user_a = User(
        username="rec_a",
        hashed_password=hash_password("StrongPass123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 1, 1),
    )
    user_b = User(
        username="rec_b",
        hashed_password=hash_password("StrongPass123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 1, 1),
    )
    session.add_all([user_a, user_b])
    session.commit()
    session.refresh(user_a)
    session.refresh(user_b)

    # User A has a custom exercise targeting chest; User B should never be recommended it
    custom_a = ExerciseCatalogItem(
        name="A Custom Chest Press",
        category="strength",
        default_met=5.0,
        equipment="bodyweight",
        level="beginner",
        is_custom=True,
        user_id=user_a.id,
    )
    session.add(custom_a)
    session.commit()
    session.refresh(custom_a)
    session.add(
        ExerciseMuscleMapping(
            exercise_catalog_id=custom_a.id,
            muscle_group="chest",
            role="primary",
            movement_pattern="horizontal_push",
        )
    )
    session.commit()

    goal_b = UserGoal(
        user_id=user_b.id,
        goal_type="build_muscle",
        training_experience="beginner",
        available_equipment="bodyweight",
    )
    session.add(goal_b)
    session.commit()

    # With only User A's custom exercise in the catalog, User B gets no recommendation
    rec_b = get_recommendation(session, user_b, today=date(2026, 11, 1), rec_type="exercise")
    assert rec_b.has_recommendation is False

    # Beginner prefers level == "beginner" over "advanced" when otherwise equal
    adv_push = ExerciseCatalogItem(
        name="Planche Push-up",
        category="strength",
        default_met=5.0,
        equipment="bodyweight",
        level="advanced",
        is_custom=False,
    )
    beg_push = ExerciseCatalogItem(
        name="Standard Push-up",
        category="strength",
        default_met=5.0,
        equipment="bodyweight",
        level="beginner",
        is_custom=False,
    )
    session.add_all([adv_push, beg_push])
    session.commit()
    session.refresh(adv_push)
    session.refresh(beg_push)
    for item in (adv_push, beg_push):
        session.add(
            ExerciseMuscleMapping(
                exercise_catalog_id=item.id,
                muscle_group="chest",
                role="primary",
                movement_pattern="horizontal_push",
            )
        )
    session.commit()

    rec_level = get_recommendation(session, user_b, today=date(2026, 11, 1), rec_type="exercise")
    assert rec_level.has_recommendation is True
    assert rec_level.items[0].name == "Standard Push-up"
    assert rec_level.items[0].exercise_catalog_id == beg_push.id


def test_recommender_yesterday_penalty_and_daily_rotation(session: Session):
    from src.auth.auth import hash_password
    from src.models import Exercise, User, UserGoal
    from src.services.recommendation_service import get_recommendation

    user = User(
        username="rec_rot",
        hashed_password=hash_password("StrongPass123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 1, 1),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    goal = UserGoal(
        user_id=user.id,
        goal_type="build_muscle",
        training_experience="beginner",
        available_equipment="bodyweight",
    )
    session.add(goal)

    # Three equal candidates
    cands = []
    for name in ("Chest A", "Chest B", "Chest C"):
        it = ExerciseCatalogItem(
            name=name,
            category="strength",
            default_met=4.5,
            equipment="bodyweight",
            level="beginner",
            is_custom=False,
        )
        session.add(it)
        cands.append(it)
    session.commit()
    for it in cands:
        session.refresh(it)
        session.add(
            ExerciseMuscleMapping(
                exercise_catalog_id=it.id,
                muscle_group="chest",
                role="primary",
                movement_pattern="horizontal_push",
            )
        )
    session.commit()

    # Over 14 consecutive days, at least 2 distinct picks, and deterministic per day
    base_day = date(2026, 11, 1)
    picks = set()
    for d in range(14):
        day = base_day + timedelta(days=d)
        r1 = get_recommendation(session, user, today=day, rec_type="exercise")
        r2 = get_recommendation(session, user, today=day, rec_type="exercise")
        assert r1.items[0].name == r2.items[0].name
        picks.add(r1.items[0].name)
    assert len(picks) >= 2

    # Exercise done yesterday ranks below an otherwise equal one
    first_pick_name = get_recommendation(session, user, today=base_day, rec_type="exercise").items[0].name
    first_item = next(c for c in cands if c.name == first_pick_name)
    session.add(
        Exercise(
            user_id=user.id,
            date=base_day - timedelta(days=1),
            name=first_item.name,
            category="strength",
            exercise_catalog_id=first_item.id,
            sets=3,
            reps=10,
            calories_burned=50.0,
            calories_burned_per_minute=5.0,
        )
    )
    session.commit()

    after_yesterday = get_recommendation(session, user, today=base_day, rec_type="exercise")
    assert after_yesterday.items[0].name != first_pick_name


