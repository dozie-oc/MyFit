from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from src.auth.auth import create_access_token
from src.database import get_session
from src.main import app
from src.models import Habit, HabitLog, User
from tests.conftest import make_test_engine

engine = make_test_engine()


def get_test_session():
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def clean_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u1 = User(id=1, username="habituser", hashed_password="hashed_pw_dummy")
        u2 = User(id=2, username="otheruser", hashed_password="hashed_pw_dummy")
        session.add(u1)
        session.add(u2)
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


@pytest.fixture
def other_user_headers():
    token = create_access_token(user_id=2)
    return {"Authorization": f"Bearer {token}"}


def test_archive_habit_via_delete_preserves_logs(client, auth_headers):
    # 1. Create habit
    create_res = client.post(
        "/habits",
        json={"name": "Drink 2L Water", "target_per_week": 7},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    habit_id = create_res.json()["id"]

    # 2. Log completions for yesterday and today
    today = date.today()
    yesterday = today - timedelta(days=1)
    client.post(
        f"/habits/{habit_id}/logs",
        json={"date": str(yesterday), "completed": True},
        headers=auth_headers,
    )
    client.post(
        f"/habits/{habit_id}/logs",
        json={"date": str(today), "completed": True},
        headers=auth_headers,
    )

    # 3. Archive habit via DELETE /habits/{habit_id}
    del_res = client.delete(f"/habits/{habit_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # 4. Active habits list should be empty
    active_res = client.get("/habits", headers=auth_headers)
    assert active_res.status_code == 200
    assert len(active_res.json()) == 0

    # 5. Archived habit is returned via dedicated endpoint and query param
    archived_res = client.get("/habits/archived", headers=auth_headers)
    assert archived_res.status_code == 200
    archived_habits = archived_res.json()
    assert len(archived_habits) == 1
    assert archived_habits[0]["id"] == habit_id
    assert archived_habits[0]["is_archived"] is True
    assert archived_habits[0]["archived_at"] is not None
    assert len(archived_habits[0]["logs"]) == 2

    # Query param ?archived=true works the same
    query_res = client.get("/habits?archived=true", headers=auth_headers)
    assert query_res.status_code == 200
    assert len(query_res.json()) == 1

    # 6. Direct GET /habits/{habit_id} and /habits/{habit_id}/logs remain accessible
    get_res = client.get(f"/habits/{habit_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["is_archived"] is True
    assert len(get_res.json()["logs"]) == 2

    logs_res = client.get(f"/habits/{habit_id}/logs", headers=auth_headers)
    assert logs_res.status_code == 200
    assert len(logs_res.json()) == 2


def test_explicit_archive_and_restore(client, auth_headers):
    # 1. Create habit
    create_res = client.post(
        "/habits",
        json={"name": "Morning Walk", "target_per_week": 5},
        headers=auth_headers,
    )
    habit_id = create_res.json()["id"]

    # 2. Archive via POST /habits/{habit_id}/archive
    archive_res = client.post(f"/habits/{habit_id}/archive", headers=auth_headers)
    assert archive_res.status_code == 200
    assert archive_res.json()["is_archived"] is True
    assert archive_res.json()["archived_at"] is not None

    # Cannot log on archived habit
    log_res = client.post(
        f"/habits/{habit_id}/logs",
        json={"date": str(date.today()), "completed": True},
        headers=auth_headers,
    )
    assert log_res.status_code == 400

    # 3. Restore via POST /habits/{habit_id}/restore
    restore_res = client.post(f"/habits/{habit_id}/restore", headers=auth_headers)
    assert restore_res.status_code == 200
    assert restore_res.json()["is_archived"] is False
    assert restore_res.json()["archived_at"] is None

    # Appears in active habits again
    active_res = client.get("/habits", headers=auth_headers)
    assert len(active_res.json()) == 1
    assert active_res.json()[0]["id"] == habit_id

    # Can log again after restoration
    log_res2 = client.post(
        f"/habits/{habit_id}/logs",
        json={"date": str(date.today()), "completed": True},
        headers=auth_headers,
    )
    assert log_res2.status_code == 200


def test_patch_archive_and_restore(client, auth_headers):
    create_res = client.post(
        "/habits",
        json={"name": "Read Book", "target_per_week": 7},
        headers=auth_headers,
    )
    habit_id = create_res.json()["id"]

    # Archive via PATCH
    patch_res = client.patch(
        f"/habits/{habit_id}",
        json={"is_archived": True},
        headers=auth_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_archived"] is True

    assert len(client.get("/habits", headers=auth_headers).json()) == 0
    assert len(client.get("/habits/archived", headers=auth_headers).json()) == 1

    # Restore via PATCH
    patch_res2 = client.patch(
        f"/habits/{habit_id}",
        json={"is_archived": False},
        headers=auth_headers,
    )
    assert patch_res2.status_code == 200
    assert patch_res2.json()["is_archived"] is False
    assert len(client.get("/habits", headers=auth_headers).json()) == 1


def test_activity_preserves_completed_and_omits_pending_for_archived(client, auth_headers):
    today = date.today()
    yesterday = today - timedelta(days=1)

    create_res = client.post(
        "/habits",
        json={"name": "Floss", "target_per_week": 7},
        headers=auth_headers,
    )
    habit_id = create_res.json()["id"]

    # Log yesterday as completed
    client.post(
        f"/habits/{habit_id}/logs",
        json={"date": str(yesterday), "completed": True},
        headers=auth_headers,
    )

    # Archive the habit today
    client.post(f"/habits/{habit_id}/archive", headers=auth_headers)

    # Fetch activity
    act_res = client.get(
        f"/habits/activity?date_from={yesterday}&date_to={today}",
        headers=auth_headers,
    )
    assert act_res.status_code == 200
    days = act_res.json()
    assert len(days) == 2

    # Yesterday: completed
    day_yesterday = next(d for d in days if d["date"] == str(yesterday))
    assert habit_id in day_yesterday["completed_habit_ids"]

    # Today: neither completed nor pending!
    day_today = next(d for d in days if d["date"] == str(today))
    assert habit_id not in day_today["completed_habit_ids"]
    assert habit_id not in day_today["pending_habit_ids"]


def test_ownership_isolation(client, auth_headers, other_user_headers):
    create_res = client.post(
        "/habits",
        json={"name": "Secret Habit", "target_per_week": 3},
        headers=auth_headers,
    )
    habit_id = create_res.json()["id"]
    client.post(f"/habits/{habit_id}/archive", headers=auth_headers)

    # User B cannot see or manipulate User A's archived habit
    assert client.get(f"/habits/{habit_id}", headers=other_user_headers).status_code == 404
    assert client.get(f"/habits/{habit_id}/logs", headers=other_user_headers).status_code == 404
    assert client.post(f"/habits/{habit_id}/restore", headers=other_user_headers).status_code == 404
    assert client.post(f"/habits/{habit_id}/archive", headers=other_user_headers).status_code == 404
    assert client.delete(f"/habits/{habit_id}", headers=other_user_headers).status_code == 404
