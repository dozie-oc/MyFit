from datetime import date as Date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import or_, select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import Habit, HabitLog
from src.schemas import (
    HABIT_COLOR_PALETTE,
    HabitActivityDay,
    HabitCreate,
    HabitLogCreate,
    HabitLogOut,
    HabitOut,
    HabitUpdate,
    HabitWithLogsOut,
)


router = APIRouter(
    prefix="/habits",
    tags=["Habits"]
)


# ============================================================
# HELPERS
# ============================================================

def _is_habit_archived(habit: Habit) -> bool:
    """Return whether the habit is currently archived."""
    return bool(habit.is_archived or habit.archived_at is not None or habit.deleted_at is not None)


def _iso_week_key(d: Date) -> tuple[int, int]:
    """Return (iso_year, iso_week) for a date."""
    iso = d.isocalendar()
    return (iso.year, iso.week)


def _build_habit_with_logs(
    habit: Habit,
    logs: list[HabitLog],
) -> HabitWithLogsOut:
    return HabitWithLogsOut(
        id=habit.id,
        name=habit.name,
        description=habit.description,
        frequency=habit.frequency,
        color=habit.color,
        target_per_week=habit.target_per_week,
        created_at=habit.created_at,
        is_archived=_is_habit_archived(habit),
        archived_at=habit.archived_at or habit.deleted_at,
        logs=[
            HabitLogOut(
                id=log.id,
                habit_id=log.habit_id,
                date=log.date,
                completed=log.completed,
            )
            for log in logs
        ],
    )


def _compute_activity(
    habits: list[Habit],
    all_logs: list[HabitLog],
    date_from: Date,
    date_to: Date,
) -> list[HabitActivityDay]:
    """
    For each day in [date_from, date_to] compute which habits are
    completed and which are still pending (eligible but not done).

    Eligibility rule: a habit is eligible on a given day if the number
    of completions in that ISO week is still below target_per_week
    *at the time that day falls* — meaning we look at completions only
    on days <= the day being evaluated within the same week.

    Archived habits never appear as pending, but their historical
    completions are retained in completed_ids.
    """
    # Group completed logs by (habit_id, iso_week)
    from collections import defaultdict
    week_completions: dict[tuple[int, int, int], list[Date]] = defaultdict(list)
    completed_on: dict[tuple[int, int], bool] = {}

    for log in all_logs:
        if log.completed:
            key = (log.habit_id, *_iso_week_key(log.date))
            week_completions[key].append(log.date)
            completed_on[(log.habit_id, log.date)] = True

    results: list[HabitActivityDay] = []
    today = Date.today()

    num_days = (date_to - date_from).days + 1
    for offset in range(num_days):
        day = date_from + timedelta(days=offset)
        completed_ids: list[int] = []
        pending_ids: list[int] = []

        for habit in habits:
            habit_start = habit.created_at.date()

            # Check completions for this habit in this ISO week
            # counting only days <= day (to reflect state as-of that day)
            wkey = (habit.id, *_iso_week_key(day))
            completions_up_to_day = [
                d for d in week_completions.get(wkey, [])
                if d <= day
            ]
            done_today = completed_on.get((habit.id, day), False)

            if done_today:
                completed_ids.append(habit.id)
            elif day >= habit_start and day <= today and len(completions_up_to_day) < habit.target_per_week:
                # Archived habits never count as pending
                if not _is_habit_archived(habit):
                    pending_ids.append(habit.id)
            # else: target already met for the week, or future day → skip

        results.append(HabitActivityDay(
            date=day,
            completed_habit_ids=completed_ids,
            pending_habit_ids=pending_ids,
        ))

    return results


# ============================================================
# ENDPOINTS
# ============================================================


@router.post(
    "",
    response_model=HabitOut,
    status_code=status.HTTP_201_CREATED
)
def create_habit(
    habit_data: HabitCreate,
    session: SessionDep,
    current_user: CurrentUserDep
):
    # Auto-assign a color from the palette based on existing habit count
    if habit_data.color:
        color = habit_data.color
    else:
        existing_count = len(session.exec(
            select(Habit).where(
                Habit.user_id == current_user.id,
                Habit.deleted_at.is_(None),
                Habit.archived_at.is_(None),
                or_(Habit.is_archived.is_(False), Habit.is_archived.is_(None)),
            )
        ).all())
        color = HABIT_COLOR_PALETTE[existing_count % len(HABIT_COLOR_PALETTE)]

    habit = Habit(
        user_id=current_user.id,
        name=habit_data.name,
        description=habit_data.description,
        color=color,
        target_per_week=habit_data.target_per_week,
        frequency="weekly" if habit_data.target_per_week < 7 else "daily",
    )

    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


@router.get(
    "",
    response_model=list[HabitWithLogsOut]
)
def get_habits(
    session: SessionDep,
    current_user: CurrentUserDep,
    days: int = Query(default=35, ge=7, le=90),
    archived: bool = Query(default=False),
):
    """
    Return active habits by default (or archived habits if archived=True),
    each with their log entries for the last `days` days embedded.
    """
    if archived:
        stmt = select(Habit).where(
            Habit.user_id == current_user.id,
            or_(
                Habit.is_archived.is_(True),
                Habit.archived_at.is_not(None),
                Habit.deleted_at.is_not(None),
            )
        ).order_by(Habit.created_at)
    else:
        stmt = select(Habit).where(
            Habit.user_id == current_user.id,
            Habit.deleted_at.is_(None),
            Habit.archived_at.is_(None),
            or_(Habit.is_archived.is_(False), Habit.is_archived.is_(None)),
        ).order_by(Habit.created_at)

    habits = session.exec(stmt).all()

    if not habits:
        return []

    date_from = Date.today() - timedelta(days=days - 1)
    habit_ids = [h.id for h in habits]

    logs = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id.in_(habit_ids),
            HabitLog.user_id == current_user.id,
            HabitLog.date >= date_from,
        ).order_by(HabitLog.date)
    ).all()

    # Group logs by habit_id
    from collections import defaultdict
    logs_by_habit: dict[int, list[HabitLog]] = defaultdict(list)
    for log in logs:
        logs_by_habit[log.habit_id].append(log)

    return [
        _build_habit_with_logs(habit, logs_by_habit.get(habit.id, []))
        for habit in habits
    ]


@router.get(
    "/archived",
    response_model=list[HabitWithLogsOut]
)
def get_archived_habits(
    session: SessionDep,
    current_user: CurrentUserDep,
    days: int = Query(default=35, ge=7, le=90),
):
    """Return all archived habits with logs embedded."""
    return get_habits(session=session, current_user=current_user, days=days, archived=True)


@router.get(
    "/activity",
    response_model=list[HabitActivityDay]
)
def get_habit_activity(
    session: SessionDep,
    current_user: CurrentUserDep,
    date_from: Date = Query(default=None),
    date_to: Date = Query(default=None),
):
    """
    Return per-day habit activity for the given date range.
    Used by the home-page calendar to draw activity rings.
    Defaults to the last 42 days if no range is given.
    """
    today = Date.today()
    if date_from is None:
        date_from = today - timedelta(days=41)
    if date_to is None:
        date_to = today

    if (date_to - date_from).days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days.",
        )

    # Include all user habits to attribute historical completions correctly
    habits = session.exec(
        select(Habit).where(
            Habit.user_id == current_user.id
        ).order_by(Habit.created_at)
    ).all()

    if not habits:
        return []

    habit_ids = [h.id for h in habits]

    # Expand range by one week in each direction to get correct week boundaries
    fetch_from = date_from - timedelta(days=6)
    logs = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id.in_(habit_ids),
            HabitLog.user_id == current_user.id,
            HabitLog.date >= fetch_from,
            HabitLog.date <= date_to,
            HabitLog.completed.is_(True),
        )
    ).all()

    return _compute_activity(habits, logs, date_from, date_to)


@router.get(
    "/{habit_id}",
    response_model=HabitWithLogsOut
)
def get_habit(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    days: int = Query(default=35, ge=7, le=90),
):
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    date_from = Date.today() - timedelta(days=days - 1)
    logs = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id == habit_id,
            HabitLog.user_id == current_user.id,
            HabitLog.date >= date_from,
        ).order_by(HabitLog.date)
    ).all()

    return _build_habit_with_logs(habit, logs)


@router.patch(
    "/{habit_id}",
    response_model=HabitOut
)
def update_habit(
    habit_id: int,
    update_data: HabitUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    if update_data.name is not None:
        habit.name = update_data.name
    if update_data.description is not None:
        habit.description = update_data.description
    if update_data.color is not None:
        habit.color = update_data.color
    if update_data.target_per_week is not None:
        habit.target_per_week = update_data.target_per_week
        habit.frequency = "weekly" if update_data.target_per_week < 7 else "daily"
    if update_data.is_archived is not None:
        if update_data.is_archived:
            now = datetime.now(timezone.utc)
            habit.is_archived = True
            habit.archived_at = now
            habit.deleted_at = now
        else:
            habit.is_archived = False
            habit.archived_at = None
            habit.deleted_at = None

    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


@router.post(
    "/{habit_id}/archive",
    response_model=HabitOut
)
def archive_habit(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Explicitly archive a habit without deleting historical logs."""
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    now = datetime.now(timezone.utc)
    habit.is_archived = True
    habit.archived_at = now
    habit.deleted_at = now
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


@router.post(
    "/{habit_id}/restore",
    response_model=HabitOut
)
def restore_habit(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Restore an archived habit back to active status."""
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    habit.is_archived = False
    habit.archived_at = None
    habit.deleted_at = None
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


@router.post(
    "/{habit_id}/logs",
    response_model=HabitLogOut
)
def log_habit(
    habit_id: int,
    log_data: HabitLogCreate,
    session: SessionDep,
    current_user: CurrentUserDep
):
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    if _is_habit_archived(habit):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot log activity for an archived habit. Restore it first.",
        )

    existing_log = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id == habit_id,
            HabitLog.user_id == current_user.id,
            HabitLog.date == log_data.date
        )
    ).first()

    if existing_log:
        existing_log.completed = log_data.completed
        session.add(existing_log)
        session.commit()
        session.refresh(existing_log)
        return existing_log

    habit_log = HabitLog(
        habit_id=habit_id,
        user_id=current_user.id,
        date=log_data.date,
        completed=log_data.completed
    )

    session.add(habit_log)
    session.commit()
    session.refresh(habit_log)
    return habit_log


@router.delete(
    "/{habit_id}/logs/{log_date}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_habit_log(
    habit_id: int,
    log_date: Date,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Remove a specific daily log entry (un-complete a day)."""
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    log = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id == habit_id,
            HabitLog.user_id == current_user.id,
            HabitLog.date == log_date,
        )
    ).first()

    if log:
        session.delete(log)
        session.commit()

    return None


@router.get(
    "/{habit_id}/logs",
    response_model=list[HabitLogOut]
)
def get_habit_logs(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    logs = session.exec(
        select(HabitLog).where(
            HabitLog.habit_id == habit_id,
            HabitLog.user_id == current_user.id
        ).order_by(HabitLog.date.desc())
    ).all()

    return logs


@router.delete(
    "/{habit_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_habit(
    habit_id: int,
    session: SessionDep,
    current_user: CurrentUserDep
):
    """
    Archive habit instead of permanently deleting it or deleting its logs.
    """
    habit = session.exec(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    ).first()

    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    now = datetime.now(timezone.utc)
    habit.is_archived = True
    habit.archived_at = now
    habit.deleted_at = now
    session.add(habit)
    session.commit()
    return None