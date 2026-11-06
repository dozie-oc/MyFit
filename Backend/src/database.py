from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from src.config import settings


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

# The database URL is managed centrally through config.py.
#
# Local development:
#
#     DATABASE_URL=sqlite:///./myfit.db
#
# Later, production can use a PostgreSQL URL without changing
# application-level database logic.
DATABASE_URL = settings.database_url


# SQLite requires check_same_thread=False because FastAPI may
# interact with the database across different threads during
# request handling.
connect_args: dict = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
    }


engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,

    # Has no meaningful effect on SQLite, but is useful when this
    # engine is later pointed at PostgreSQL. It tells SQLAlchemy to
    # verify that a pooled connection is still alive before using it.
    pool_pre_ping=True,
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================


def create_db_and_tables() -> None:
    """
    Create all SQLModel tables and populate default exercise catalogue.
    """

    SQLModel.metadata.create_all(engine)

    # Backward compatibility for existing SQLite databases without Alembic:
    # Add new columns to existing tables if they don't already exist.
    with engine.connect() as conn:
        from sqlalchemy import text

        # Note on effort_rating migration:
        # We add `effort_rating` (1-5 scale, NULL when unknown) without converting
        # legacy `rir` columns, so historical records remain valid with
        # `effort_rating = None` rather than inventing synthetic effort ratings.
        _safe_alter_table_migrations = [
            "ALTER TABLE meal ADD COLUMN meal_type VARCHAR(20) DEFAULT 'snack'",
            "ALTER TABLE meals ADD COLUMN meal_type VARCHAR(20) DEFAULT 'snack'",
            "ALTER TABLE exercise ADD COLUMN effort_rating INTEGER",
            "ALTER TABLE exercises ADD COLUMN effort_rating INTEGER",
            "ALTER TABLE exercise ADD COLUMN workout_session_id INTEGER REFERENCES workoutsession(id)",
            "ALTER TABLE exercises ADD COLUMN workout_session_id INTEGER REFERENCES workout_sessions(id)",
        ]
        for migration in _safe_alter_table_migrations:
            try:
                conn.execute(text(migration))
                conn.commit()
            except Exception:
                pass

    with Session(engine) as session:
        seed_exercise_catalog(session)


def seed_exercise_catalog(session: Session) -> None:
    """
    Seed and update standard exercise catalog items and muscle mappings
    idempotently from exercise_catalog_data.CATALOG.
    """
    from sqlmodel import select
    from src.exercise_catalog_data import CATALOG
    from src.models import ExerciseCatalogItem, ExerciseMuscleMapping

    standard_items = session.exec(
        select(ExerciseCatalogItem).where(
            ExerciseCatalogItem.is_custom == False,  # noqa: E712
        )
    ).all()
    by_lower_name: dict[str, ExerciseCatalogItem] = {
        item.name.lower(): item for item in standard_items
    }

    for entry in CATALOG:
        key = entry["name"].lower()
        existing_item = by_lower_name.get(key)
        if existing_item is None:
            new_item = ExerciseCatalogItem(
                name=entry["name"],
                category=entry["category"],
                default_met=entry["met"],
                description=entry["description"],
                equipment=entry["equipment"],
                level=entry["level"],
                is_custom=False,
            )
            session.add(new_item)
            by_lower_name[key] = new_item
        else:
            existing_item.default_met = entry["met"]
            existing_item.description = entry["description"]
            existing_item.equipment = entry["equipment"]
            existing_item.level = entry["level"]
            existing_item.deleted_at = None
            session.add(existing_item)

    session.flush()

    existing_mappings = session.exec(select(ExerciseMuscleMapping)).all()
    mapping_by_pair: dict[tuple[int, str], ExerciseMuscleMapping] = {
        (m.exercise_catalog_id, m.muscle_group): m for m in existing_mappings
    }

    for entry in CATALOG:
        catalog_item = by_lower_name.get(entry["name"].lower())
        if not catalog_item or catalog_item.id is None:
            continue
        for muscle_group, role, movement_pattern in entry["muscles"]:
            pair = (catalog_item.id, muscle_group)
            existing_m = mapping_by_pair.get(pair)
            if existing_m is None:
                new_m = ExerciseMuscleMapping(
                    exercise_catalog_id=catalog_item.id,
                    muscle_group=muscle_group,
                    role=role,
                    movement_pattern=movement_pattern,
                )
                session.add(new_m)
                mapping_by_pair[pair] = new_m
            else:
                if existing_m.role != role or existing_m.movement_pattern != movement_pattern:
                    existing_m.role = role
                    existing_m.movement_pattern = movement_pattern
                    session.add(existing_m)

    session.commit()


# ============================================================
# FASTAPI DATABASE DEPENDENCY
# ============================================================


def get_session() -> Generator[Session, None, None]:
    """
    Provide a database session to a FastAPI request.

    The session is automatically closed when the request finishes,
    even if the endpoint raises an exception.
    """

    with Session(engine) as session:
        yield session