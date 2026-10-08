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

        _safe_alter_table_migrations = [
            "ALTER TABLE meal ADD COLUMN meal_type VARCHAR(20) DEFAULT 'snack'",
            "ALTER TABLE exercise ADD COLUMN rir INTEGER",
            "ALTER TABLE exercise ADD COLUMN workout_session_id INTEGER REFERENCES workoutsession(id)",
        ]
        for migration in _safe_alter_table_migrations:
            try:
                conn.execute(text(migration))
                conn.commit()
            except Exception:
                pass

    from src.models import ExerciseCatalogItem, ExerciseMuscleMapping
    from sqlmodel import select

    with Session(engine) as session:
        existing = session.exec(select(ExerciseCatalogItem)).first()
        if not existing:
            default_catalog = [
                # Cardio
                ExerciseCatalogItem(name="Running", category="cardio", default_met=9.8, description="Outdoor or treadmill running"),
                ExerciseCatalogItem(name="Cycling", category="cardio", default_met=7.5, description="Road, stationary, or mountain biking"),
                ExerciseCatalogItem(name="Swimming", category="cardio", default_met=7.0, description="Freestyle, breaststroke, laps"),
                ExerciseCatalogItem(name="Walking", category="cardio", default_met=3.8, description="Brisk walking or incline treadmill"),
                ExerciseCatalogItem(name="Jump Rope", category="cardio", default_met=11.0, description="High-intensity rope jumping"),
                ExerciseCatalogItem(name="HIIT", category="cardio", default_met=8.0, description="High-Intensity Interval Training"),
                ExerciseCatalogItem(name="Rowing Machine", category="cardio", default_met=7.0, description="Indoor rowing workout"),
                ExerciseCatalogItem(name="Elliptical", category="cardio", default_met=6.5, description="Elliptical cross trainer"),
                # Strength
                ExerciseCatalogItem(name="Bench Press", category="strength", default_met=5.0, description="Barbell flat bench press for chest"),
                ExerciseCatalogItem(name="Barbell Squat", category="strength", default_met=5.0, description="Back or front barbell squats for legs"),
                ExerciseCatalogItem(name="Deadlift", category="strength", default_met=5.5, description="Conventional or sumo barbell deadlifts"),
                ExerciseCatalogItem(name="Overhead Press", category="strength", default_met=5.0, description="Standing or seated shoulder press"),
                ExerciseCatalogItem(name="Barbell Row", category="strength", default_met=5.0, description="Bent-over barbell rows for upper back"),
                ExerciseCatalogItem(name="Dumbbell Curl", category="strength", default_met=4.5, description="Bicep curls with dumbbells"),
                ExerciseCatalogItem(name="Push-ups", category="strength", default_met=4.5, description="Bodyweight push-ups"),
                ExerciseCatalogItem(name="Pull-ups", category="strength", default_met=5.0, description="Bodyweight or weighted pull-ups / chin-ups"),
                ExerciseCatalogItem(name="Dips", category="strength", default_met=4.5, description="Parallel bar dips for triceps and chest"),
                ExerciseCatalogItem(name="Plank", category="strength", default_met=3.5, description="Isometric core plank"),
                ExerciseCatalogItem(name="Leg Press", category="strength", default_met=5.0, description="Machine leg press"),
                # Flexibility
                ExerciseCatalogItem(name="Yoga", category="flexibility", default_met=2.8, description="Hatha, Vinyasa, or restorative yoga"),
                ExerciseCatalogItem(name="Pilates", category="flexibility", default_met=3.0, description="Mat or reformer pilates"),
                ExerciseCatalogItem(name="Stretching", category="flexibility", default_met=2.5, description="Full-body mobility and flexibility routine"),
            ]
            session.add_all(default_catalog)
            session.commit()

        # Seed muscle group mappings for standard catalog exercises.
        # Only runs if the mapping table is empty, so existing databases
        # that already have catalog items get the mappings populated too.
        existing_mappings = session.exec(select(ExerciseMuscleMapping)).first()
        if not existing_mappings:
            _seed_muscle_mappings(session)


def _seed_muscle_mappings(session: Session) -> None:
    """
    Populate muscle-group mappings for all standard exercise catalog items.

    This mapping data is the foundation for training volume calculations
    and workout adequacy evaluation.

    Each tuple is: (exercise_name, muscle_group, role, movement_pattern)
    """
    from src.models import ExerciseCatalogItem, ExerciseMuscleMapping
    from sqlmodel import select

    # Mapping definitions: exercise_name -> [(muscle_group, role, movement_pattern)]
    MAPPING_DATA: dict[str, list[tuple[str, str, str]]] = {
        # ── Strength exercises ──────────────────────────────
        "Bench Press": [
            ("chest", "primary", "horizontal_push"),
            ("triceps", "secondary", "horizontal_push"),
            ("shoulders", "secondary", "horizontal_push"),
        ],
        "Barbell Squat": [
            ("quadriceps", "primary", "squat"),
            ("glutes", "primary", "squat"),
            ("hamstrings", "secondary", "squat"),
        ],
        "Deadlift": [
            ("hamstrings", "primary", "hinge"),
            ("glutes", "primary", "hinge"),
            ("back", "secondary", "hinge"),
            ("forearms", "secondary", "hinge"),
        ],
        "Overhead Press": [
            ("shoulders", "primary", "vertical_push"),
            ("triceps", "secondary", "vertical_push"),
        ],
        "Barbell Row": [
            ("back", "primary", "horizontal_pull"),
            ("biceps", "secondary", "horizontal_pull"),
        ],
        "Dumbbell Curl": [
            ("biceps", "primary", "isolation"),
            ("forearms", "secondary", "isolation"),
        ],
        "Push-ups": [
            ("chest", "primary", "horizontal_push"),
            ("triceps", "secondary", "horizontal_push"),
            ("shoulders", "secondary", "horizontal_push"),
        ],
        "Pull-ups": [
            ("back", "primary", "vertical_pull"),
            ("biceps", "secondary", "vertical_pull"),
        ],
        "Dips": [
            ("triceps", "primary", "vertical_push"),
            ("chest", "secondary", "vertical_push"),
            ("shoulders", "secondary", "vertical_push"),
        ],
        "Plank": [
            ("abs_core", "primary", "core"),
        ],
        "Leg Press": [
            ("quadriceps", "primary", "squat"),
            ("glutes", "secondary", "squat"),
        ],
        # ── Cardio exercises (no resistance-training muscle mappings) ──
        # Cardio exercises are intentionally left WITHOUT muscle mappings.
        # They use duration/distance/MET for their own adequacy model
        # and should NOT contribute resistance-training set counts.
    }

    # Look up catalog items and create mappings
    catalog_items = session.exec(
        select(ExerciseCatalogItem).where(
            ExerciseCatalogItem.is_custom == False,
            ExerciseCatalogItem.deleted_at.is_(None),
        )
    ).all()

    catalog_by_name = {item.name: item for item in catalog_items}
    mappings_to_add = []

    for exercise_name, muscle_entries in MAPPING_DATA.items():
        catalog_item = catalog_by_name.get(exercise_name)
        if not catalog_item:
            continue
        for muscle_group, role, movement_pattern in muscle_entries:
            mappings_to_add.append(
                ExerciseMuscleMapping(
                    exercise_catalog_id=catalog_item.id,
                    muscle_group=muscle_group,
                    role=role,
                    movement_pattern=movement_pattern,
                )
            )

    if mappings_to_add:
        session.add_all(mappings_to_add)
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