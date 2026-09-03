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

    from src.models import ExerciseCatalogItem
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