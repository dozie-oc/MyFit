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


def test_patch_exercise_recomputes_calories_summary_dates_and_relinks(
    session: Session, client: TestClient
):
    from src.models import DailySummary

    seed_exercise_catalog(session)
    headers_a = _headers(client, "q4_user_a")
    headers_b = _headers(client, "q4_user_b")

    d1 = "2026-10-20"
    d2 = "2026-10-21"

    # Log Bench Press on d1
    create_res = client.post(
        "/exercises",
        headers=headers_a,
        json={
            "date": d1,
            "name": "Bench Press",
            "category": "strength",
            "sets": 3,
            "reps": 8,
            "weight_kg": 60.0,
        },
    )
    assert create_res.status_code == 201
    ex = create_res.json()
    ex_id = ex["id"]
    orig_cal = ex["calories_burned"]
    orig_cat_id = ex["exercise_catalog_id"]
    assert orig_cat_id is not None

    # Editing sets recomputes calories and daily summary
    patch_res = client.patch(
        f"/exercises/{ex_id}",
        headers=headers_a,
        json={"sets": 6},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["sets"] == 6
    assert updated["calories_burned"] > orig_cal

    sum_d1 = session.exec(
        select(DailySummary).where(DailySummary.date == date.fromisoformat(d1))
    ).first()
    assert sum_d1 is not None
    assert sum_d1.calories_out == int(updated["calories_burned"])

    # Moving to another date updates both days
    move_res = client.patch(
        f"/exercises/{ex_id}",
        headers=headers_a,
        json={"date": d2},
    )
    assert move_res.status_code == 200
    session.expire_all()
    sum_d1_after = session.exec(
        select(DailySummary).where(DailySummary.date == date.fromisoformat(d1))
    ).first()
    sum_d2_after = session.exec(
        select(DailySummary).where(DailySummary.date == date.fromisoformat(d2))
    ).first()
    assert sum_d1_after.calories_out == 0
    assert sum_d2_after.calories_out == int(updated["calories_burned"])

    # Name change relinks catalog item
    relink_res = client.patch(
        f"/exercises/{ex_id}",
        headers=headers_a,
        json={"name": "Pull-ups"},
    )
    assert relink_res.status_code == 200
    relinked = relink_res.json()
    assert relinked["name"] == "Pull-ups"
    assert relinked["exercise_catalog_id"] is not None
    assert relinked["exercise_catalog_id"] != orig_cat_id

    # User B gets 404
    b_res = client.patch(
        f"/exercises/{ex_id}",
        headers=headers_b,
        json={"sets": 4},
    )
    assert b_res.status_code == 404

    # Invalid values give 422
    bad_res = client.patch(
        f"/exercises/{ex_id}",
        headers=headers_a,
        json={"sets": -1},
    )
    assert bad_res.status_code == 422


def test_q5_epley_pr_and_history(session: Session):
    from fastapi import HTTPException
    from src.auth.auth import hash_password
    from src.models import User
    from src.routers.exercises import (
        _est_1rm,
        create_exercise,
        delete_exercise,
        get_exercise_history,
        update_exercise,
    )
    from src.schemas import ExerciseLogCreate, ExerciseLogUpdate

    seed_exercise_catalog(session)

    # Epley values: weight * (1 + reps / 30)
    assert round(_est_1rm(100.0, 10), 2) == round(100.0 * (1 + 10 / 30), 2)
    assert _est_1rm(60.0, 15) == 90.0

    user_a = User(
        username="q5_a",
        hashed_password=hash_password("StrongPass123!"),
        weight=75.0,
        height=180.0,
        birthdate=date(1995, 1, 1),
    )
    user_b = User(
        username="q5_b",
        hashed_password=hash_password("StrongPass123!"),
        weight=75.0,
        height=180.0,
        birthdate=date(1995, 1, 1),
    )
    session.add_all([user_a, user_b])
    session.commit()
    session.refresh(user_a)
    session.refresh(user_b)

    # Requires at least one parameter
    with pytest.raises(HTTPException) as exc_info:
        get_exercise_history(session=session, current_user=user_a, exercise_catalog_id=None, name=None)
    assert exc_info.value.status_code == 422

    # First log is never a PR
    log1 = create_exercise(
        ExerciseLogCreate(
            date=date(2026, 10, 1),
            name="Bench Press",
            category="strength",
            sets=3,
            reps=8,
            weight_kg=60.0,
        ),
        session=session,
        current_user=user_a,
    )
    assert log1.is_pr is False

    # Second log with higher 1RM is a PR
    log2 = create_exercise(
        ExerciseLogCreate(
            date=date(2026, 10, 2),
            name="Bench Press",
            category="strength",
            sets=3,
            reps=8,
            weight_kg=65.0,
        ),
        session=session,
        current_user=user_a,
    )
    assert log2.is_pr is True

    # Third log with lower 1RM is NOT a PR
    log3 = create_exercise(
        ExerciseLogCreate(
            date=date(2026, 10, 3),
            name="Bench Press",
            category="strength",
            sets=3,
            reps=5,
            weight_kg=60.0,
        ),
        session=session,
        current_user=user_a,
    )
    assert log3.is_pr is False

    # Patching log3 to beat log2 sets is_pr=True
    patched = update_exercise(
        log3.id,
        ExerciseLogUpdate(weight_kg=70.0, reps=8),
        session=session,
        current_user=user_a,
    )
    assert patched.is_pr is True

    # User B logs a huge weight; User A's history ignores User B
    create_exercise(
        ExerciseLogCreate(
            date=date(2026, 10, 4),
            name="Bench Press",
            category="strength",
            sets=3,
            reps=10,
            weight_kg=150.0,
        ),
        session=session,
        current_user=user_b,
    )

    # Soft-delete log3; history should ignore deleted rows
    delete_exercise(log3.id, session=session, current_user=user_a)

    hist = get_exercise_history(
        session=session,
        current_user=user_a,
        exercise_catalog_id=log1.exercise_catalog_id,
        name=None,
    )
    assert hist.times_logged == 2
    assert hist.last is not None
    assert hist.last.id == log2.id
    assert hist.best_weight_kg == 65.0
    assert hist.best_est_1rm == round(65.0 * (1 + 8 / 30), 1)

    # Name fallback is case-insensitive when no catalog_id is given
    create_exercise(
        ExerciseLogCreate(
            date=date(2026, 10, 5),
            name="Atlas Stone Lift",
            category="strength",
            sets=3,
            reps=5,
            weight_kg=80.0,
        ),
        session=session,
        current_user=user_a,
    )
    hist_name = get_exercise_history(
        session=session,
        current_user=user_a,
        exercise_catalog_id=None,
        name="atlas stone lift",
    )
    assert hist_name.times_logged == 1
    assert hist_name.best_weight_kg == 80.0


def test_q5_recommender_suggested_load(session: Session):
    from src.auth.auth import hash_password
    from src.models import Exercise, User, UserGoal
    from src.services.recommendation_service import get_recommendation

    user = User(
        username="q5_rec",
        hashed_password=hash_password("StrongPass123!"),
        weight=75.0,
        height=180.0,
        birthdate=date(1995, 1, 1),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    goal = UserGoal(
        user_id=user.id,
        goal_type="build_muscle",
        training_experience="intermediate",  # target_reps = 8
        available_equipment="barbell",
    )
    session.add(goal)

    bench = ExerciseCatalogItem(
        name="Bench Press",
        category="strength",
        default_met=5.0,
        equipment="barbell",
        level="intermediate",
        is_custom=False,
    )
    session.add(bench)
    session.commit()
    session.refresh(bench)
    session.add(
        ExerciseMuscleMapping(
            exercise_catalog_id=bench.id,
            muscle_group="chest",
            role="primary",
            movement_pattern="horizontal_push",
        )
    )
    session.commit()

    today = date(2026, 11, 1)

    # 1. No history -> no weight_kg or last_performance
    rec0 = get_recommendation(session, user, today=today, rec_type="exercise")
    assert rec0.items[0].weight_kg is None
    assert rec0.items[0].last_performance is None

    # 2. History with reps >= target_reps (8) and rir >= 1 -> suggest weight + 2.5
    ex1 = Exercise(
        user_id=user.id,
        date=today - timedelta(days=3),
        name="Bench Press",
        category="strength",
        exercise_catalog_id=bench.id,
        sets=4,
        reps=8,
        weight_kg=60.0,
        rir=2,
        calories_burned=80.0,
        calories_burned_per_minute=5.0,
    )
    session.add(ex1)
    session.commit()

    rec1 = get_recommendation(session, user, today=today, rec_type="exercise")
    assert rec1.items[0].weight_kg == 62.5
    assert rec1.items[0].last_performance is not None
    assert "60" in rec1.items[0].last_performance
    assert "3 days ago" in rec1.items[0].last_performance
    assert "62.5" in rec1.reason
    assert rec1.items[0].last_performance in rec1.reason

    # 3. History with reps < target_reps (or rir == 0) -> suggest same weight
    ex2 = Exercise(
        user_id=user.id,
        date=today - timedelta(days=1),
        name="Bench Press",
        category="strength",
        exercise_catalog_id=bench.id,
        sets=4,
        reps=6,
        weight_kg=62.5,
        rir=0,
        calories_burned=80.0,
        calories_burned_per_minute=5.0,
    )
    session.add(ex2)
    session.commit()

    rec2 = get_recommendation(session, user, today=today, rec_type="exercise")
    assert rec2.items[0].weight_kg == 62.5


def test_q7_custom_exercises(session: Session):
    from fastapi import HTTPException
    from pydantic import ValidationError
    from src.auth.auth import hash_password
    from src.models import User, UserGoal
    from src.routers.exercises import (
        create_custom_exercise,
        create_exercise,
        delete_custom_exercise,
        get_exercise_catalog,
        get_training_adequacy,
        update_custom_exercise,
    )
    from src.schemas import (
        CustomExerciseCreate,
        CustomExerciseMuscleInput,
        CustomExerciseUpdate,
        ExerciseLogCreate,
    )
    from src.services.recommendation_service import get_recommendation

    seed_exercise_catalog(session)

    user_a = User(
        username="q7_a",
        hashed_password=hash_password("StrongPass123!"),
        weight=75.0,
        height=180.0,
        birthdate=date(1995, 1, 1),
    )
    user_b = User(
        username="q7_b",
        hashed_password=hash_password("StrongPass123!"),
        weight=75.0,
        height=180.0,
        birthdate=date(1995, 1, 1),
    )
    session.add_all([user_a, user_b])
    session.commit()
    session.refresh(user_a)
    session.refresh(user_b)

    # Validation: strength without a primary fails (ValidationError -> 422)
    with pytest.raises(ValidationError):
        CustomExerciseCreate(
            name="Bad Strength",
            category="strength",
            muscles=[CustomExerciseMuscleInput(muscle_group="chest", role="secondary")],
        )

    # Validation: non-strength with muscles fails
    with pytest.raises(ValidationError):
        CustomExerciseCreate(
            name="Bad Cardio",
            category="cardio",
            muscles=[CustomExerciseMuscleInput(muscle_group="chest", role="primary")],
        )

    # Validation: unknown muscle group fails
    with pytest.raises(ValidationError):
        CustomExerciseCreate(
            name="Unknown Muscle",
            category="strength",
            muscles=[CustomExerciseMuscleInput(muscle_group="wings", role="primary")],
        )

    # Create valid custom strength exercise for User A
    created = create_custom_exercise(
        CustomExerciseCreate(
            name="Ring Push-up",
            category="strength",
            equipment="bodyweight",
            level="intermediate",
            muscles=[
                CustomExerciseMuscleInput(muscle_group="chest", role="primary"),
                CustomExerciseMuscleInput(muscle_group="triceps", role="secondary"),
            ],
        ),
        session=session,
        current_user=user_a,
    )
    assert created.is_custom is True
    assert created.default_met == 5.0
    assert len(created.muscles) == 2

    # Duplicate name (own custom or standard catalog, case-insensitive) gives 409
    with pytest.raises(HTTPException) as exc_dup1:
        create_custom_exercise(
            CustomExerciseCreate(
                name="ring push-up",
                category="strength",
                muscles=[CustomExerciseMuscleInput(muscle_group="chest", role="primary")],
            ),
            session=session,
            current_user=user_a,
        )
    assert exc_dup1.value.status_code == 409

    with pytest.raises(HTTPException) as exc_dup2:
        create_custom_exercise(
            CustomExerciseCreate(
                name="bench press",
                category="strength",
                muscles=[CustomExerciseMuscleInput(muscle_group="chest", role="primary")],
            ),
            session=session,
            current_user=user_a,
        )
    assert exc_dup2.value.status_code == 409

    # Catalog list includes own custom and excludes others'
    cat_a = get_exercise_catalog(session=session, current_user=user_a)
    cat_b = get_exercise_catalog(session=session, current_user=user_b)
    assert any(i.id == created.id for i in cat_a)
    assert not any(i.id == created.id for i in cat_b)

    # User B can't patch, delete, or log with User A's custom exercise
    with pytest.raises(HTTPException) as exc_patch_b:
        update_custom_exercise(
            created.id,
            CustomExerciseUpdate(name="Hacked"),
            session=session,
            current_user=user_b,
        )
    assert exc_patch_b.value.status_code == 404

    with pytest.raises(HTTPException) as exc_del_b:
        delete_custom_exercise(created.id, session=session, current_user=user_b)
    assert exc_del_b.value.status_code == 404

    with pytest.raises(HTTPException) as exc_log_b:
        create_exercise(
            ExerciseLogCreate(
                date=date.today(),
                name="Ring Push-up",
                category="strength",
                exercise_catalog_id=created.id,
                sets=3,
                reps=10,
            ),
            session=session,
            current_user=user_b,
        )
    assert exc_log_b.value.status_code == 400

    # User B is never recommended User A's custom exercise
    rec_b = get_recommendation(session, user_b, today=date.today(), rec_type="exercise")
    assert all(it.exercise_catalog_id != created.id for it in rec_b.items)

    # User A logs 3 sets of custom exercise -> shows effective sets on chest in adequacy
    create_exercise(
        ExerciseLogCreate(
            date=date.today(),
            name="Ring Push-up",
            category="strength",
            exercise_catalog_id=created.id,
            sets=3,
            reps=10,
        ),
        session=session,
        current_user=user_a,
    )
    adeq = get_training_adequacy(session=session, current_user=user_a)
    mg = {m.muscle_group: m for m in adeq.muscle_groups}
    assert mg["chest"].sets_completed == 3.0
    assert mg["triceps"].sets_completed == 1.5

    # Patch custom exercise muscles
    updated = update_custom_exercise(
        created.id,
        CustomExerciseUpdate(
            muscles=[CustomExerciseMuscleInput(muscle_group="chest", role="primary")]
        ),
        session=session,
        current_user=user_a,
    )
    assert len(updated.muscles) == 1

    # Soft delete custom exercise: earlier logs and their volume remain
    delete_custom_exercise(created.id, session=session, current_user=user_a)
    cat_a_after = get_exercise_catalog(session=session, current_user=user_a)
    assert not any(i.id == created.id for i in cat_a_after)

    adeq_after = get_training_adequacy(session=session, current_user=user_a)
    mg_after = {m.muscle_group: m for m in adeq_after.muscle_groups}
    assert mg_after["chest"].sets_completed == 3.0


def test_q9_weekly_cardio(session: Session):
    from src.auth.auth import hash_password
    from src.models import Exercise, User, UserGoal
    from src.services.training_service import evaluate_training_adequacy

    user = User(
        username="q9_user",
        hashed_password=hash_password("StrongPass123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 1, 1),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # 2026-10-26 is Monday, 2026-10-25 is previous Sunday, 2026-10-28 is Wednesday
    sunday_prev = date(2026, 10, 25)
    monday = date(2026, 10, 26)
    wednesday = date(2026, 10, 28)

    # Default target (build_muscle -> 90 min)
    goal_muscle = UserGoal(user_id=user.id, goal_type="build_muscle")
    session.add(goal_muscle)
    session.commit()

    # Log on previous Sunday -> should NOT count in Monday..Wednesday window
    session.add(
        Exercise(
            user_id=user.id,
            date=sunday_prev,
            name="Running",
            category="cardio",
            duration_minutes=60,
            intensity="high",
            calories_burned=500.0,
            calories_burned_per_minute=8.3,
        )
    )
    session.commit()

    adeq0 = evaluate_training_adequacy(session, user.id, goal_muscle, today=wednesday)
    assert adeq0.cardio_week.target_minutes == 90
    assert adeq0.cardio_week.minutes == 0.0
    assert adeq0.cardio_week.status == "low"

    # Intensity weighting: 20 min low (10) + 20 min moderate (20) + 10 min high (20) = 50 min
    # For target 90: 50 >= 45 (50%) -> "building"
    session.add_all(
        [
            Exercise(
                user_id=user.id,
                date=monday,
                name="Walking",
                category="cardio",
                duration_minutes=20,
                intensity="low",
                calories_burned=80.0,
                calories_burned_per_minute=4.0,
            ),
            Exercise(
                user_id=user.id,
                date=monday,
                name="Cycling",
                category="cardio",
                duration_minutes=20,
                intensity="moderate",
                calories_burned=140.0,
                calories_burned_per_minute=7.0,
            ),
            Exercise(
                user_id=user.id,
                date=wednesday,
                name="HIIT",
                category="cardio",
                duration_minutes=10,
                intensity="high",
                calories_burned=120.0,
                calories_burned_per_minute=12.0,
            ),
        ]
    )
    session.commit()

    adeq1 = evaluate_training_adequacy(session, user.id, goal_muscle, today=wednesday)
    assert adeq1.cardio_week.minutes == 50.0
    assert adeq1.cardio_week.status == "building"

    # Switch goal to lose_weight (target 150): 50 < 75 -> "low"
    goal_muscle.goal_type = "lose_weight"
    session.add(goal_muscle)
    session.commit()

    adeq2 = evaluate_training_adequacy(session, user.id, goal_muscle, today=wednesday)
    assert adeq2.cardio_week.target_minutes == 150
    assert adeq2.cardio_week.status == "low"

    # Add 50 min high intensity (+100 equiv min -> total 150) -> "met"
    session.add(
        Exercise(
            user_id=user.id,
            date=wednesday,
            name="Running",
            category="cardio",
            duration_minutes=50,
            intensity="high",
            calories_burned=500.0,
            calories_burned_per_minute=10.0,
        )
    )
    session.commit()

    adeq3 = evaluate_training_adequacy(session, user.id, goal_muscle, today=wednesday)
    assert adeq3.cardio_week.minutes == 150.0
    assert adeq3.cardio_week.status == "met"


def test_q10_recipe_totals_and_food_search_escape(session: Session):
    from src.auth.auth import hash_password
    from src.models import FoodItem, User
    from src.routers.foods import create_custom_food, search_local_foods, update_custom_food
    from src.routers.recipes import create_recipe, get_recipe, update_recipe
    from src.schemas import CustomFoodCreate, CustomFoodUpdate, MealItemCreate, RecipeCreate

    user = User(
        username="q10_user",
        hashed_password=hash_password("StrongPass123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 1, 1),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create a custom food ingredient
    ing_food = create_custom_food(
        CustomFoodCreate(
            name="Special Oats",
            basis="per_100g",
            calories=400.0,
            protein=15.0,
            carbs=65.0,
            fat=8.0,
        ),
        session=session,
        current_user=user,
    )

    recipe_in = RecipeCreate(
        name="Oat Bowl",
        servings=2,
        ingredients=[
            MealItemCreate(food_id=ing_food.id, quantity=100.0, unit="g")
        ],
    )
    rec = create_recipe(recipe_in, session=session, current_user=user)
    assert rec.total_calories == 400.0
    assert rec.calories_per_portion == 200.0

    # Edit the ingredient custom food; recipe detail totals don't change until recipe is saved again
    update_custom_food(
        ing_food.id,
        CustomFoodUpdate(calories=300.0),
        session=session,
        current_user=user,
    )
    rec_detail = get_recipe(rec.food_id, session=session, current_user=user)
    assert rec_detail.total_calories == 400.0
    assert rec_detail.calories_per_portion == 200.0
    assert rec_detail.ingredients[0].calories == 300.0  # ingredient row keeps live value

    # Saving the recipe again updates the totals
    rec_updated = update_recipe(rec.food_id, recipe_in, session=session, current_user=user)
    assert rec_updated.total_calories == 300.0
    assert rec_updated.calories_per_portion == 150.0

    # Searching '%' returns nothing unless a food name contains a literal '%'
    res_pct = search_local_foods(session=session, current_user=user, q="%", limit=20)
    assert res_pct == []

    create_custom_food(
        CustomFoodCreate(
            name="2% Milk",
            basis="per_100g",
            calories=50.0,
            protein=3.4,
            carbs=4.8,
            fat=2.0,
        ),
        session=session,
        current_user=user,
    )
    res_pct2 = search_local_foods(session=session, current_user=user, q="%", limit=20)
    assert [f.name for f in res_pct2] == ["2% Milk"]


def test_q11_foods_to_avoid(session: Session):
    from src.auth.auth import hash_password
    from src.models import FoodItem, User, UserGoal
    from src.routers.foods import get_foods, search_local_foods
    from src.services.food_access import matches_avoid, parse_avoid_terms
    from src.services.recommendation_service import get_recommendation

    # 1. Unit tests for parse_avoid_terms and matches_avoid
    terms = parse_avoid_terms("Dairy, nuts; eggs\nshellfish and rice")
    assert terms == ["dairy", "nuts", "eggs", "shellfish", "rice"]

    # "dairy" excludes Greek Yogurt and Milk
    assert matches_avoid("Greek Yogurt", ["dairy"]) is True
    assert matches_avoid("Milk", ["dairy"]) is True

    # "nuts" excludes Peanut Butter and Almonds
    assert matches_avoid("Peanut Butter", ["nuts"]) is True
    assert matches_avoid("Almonds", ["nuts"]) is True

    # "eggs" excludes Egg
    assert matches_avoid("Egg", ["eggs"]) is True

    # "egg" does not exclude Eggplant
    assert matches_avoid("Eggplant", ["egg"]) is False

    # "rice" does not exclude Licorice
    assert matches_avoid("Licorice", ["rice"]) is False

    # 2. User-scoped avoided flag on list and search + recommendations skip avoided foods
    user_a = User(
        username="q11_a",
        hashed_password=hash_password("StrongPass123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 1, 1),
    )
    user_b = User(
        username="q11_b",
        hashed_password=hash_password("StrongPass123!"),
        weight=70.0,
        height=175.0,
        birthdate=date(1995, 1, 1),
    )
    session.add_all([user_a, user_b])
    session.commit()
    session.refresh(user_a)
    session.refresh(user_b)

    session.add(
        UserGoal(
            user_id=user_a.id,
            goal_type="maintain_weight",
            foods_to_avoid="dairy, nuts",
        )
    )
    f_yogurt = FoodItem(
        name="Greek Yogurt",
        calories_per_100g=59.0,
        protein_per_100g=10.0,
        carbs_per_100g=3.6,
        fat_per_100g=0.4,
        base_unit="g",
        kind="catalog",
    )
    f_almonds = FoodItem(
        name="Almonds",
        calories_per_100g=579.0,
        protein_per_100g=21.0,
        carbs_per_100g=22.0,
        fat_per_100g=50.0,
        base_unit="g",
        kind="catalog",
    )
    f_chicken = FoodItem(
        name="Chicken Breast",
        calories_per_100g=165.0,
        protein_per_100g=31.0,
        carbs_per_100g=0.0,
        fat_per_100g=3.6,
        base_unit="g",
        kind="catalog",
    )
    f_rice = FoodItem(
        name="White Rice",
        calories_per_100g=130.0,
        protein_per_100g=2.7,
        carbs_per_100g=28.0,
        fat_per_100g=0.3,
        base_unit="g",
        kind="catalog",
    )
    session.add_all([f_yogurt, f_almonds, f_chicken, f_rice])
    session.commit()

    # List and search for user_a have avoided=True on Greek Yogurt & Almonds, False on Chicken/Rice
    list_a = {f.name: f.avoided for f in get_foods(session=session, current_user=user_a, offset=0, limit=50)}
    assert list_a["Greek Yogurt"] is True
    assert list_a["Almonds"] is True
    assert list_a["Chicken Breast"] is False

    search_a = {f.name: f.avoided for f in search_local_foods(session=session, current_user=user_a, q="Greek", limit=20)}
    assert search_a["Greek Yogurt"] is True

    # User B has no foods_to_avoid -> avoided is False for all
    list_b = {f.name: f.avoided for f in get_foods(session=session, current_user=user_b, offset=0, limit=50)}
    assert list_b["Greek Yogurt"] is False
    assert list_b["Almonds"] is False

    # Recommendations for user_a skip avoided foods (Greek Yogurt and Almonds)
    rec = get_recommendation(session, user_a, today=date(2026, 11, 1), rec_type="meal")
    rec_names = {item.name for item in rec.items}
    assert "Greek Yogurt" not in rec_names
    assert "Almonds" not in rec_names








