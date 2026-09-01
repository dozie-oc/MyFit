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
#     DATABASE_URL=sqlite:///./fitness_tracker.db
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
    Create all SQLModel tables.

    This is intentionally being used for local development rather
    than Alembic migrations.

    While the schema is still changing rapidly, deleting the local
    SQLite database and restarting the application gives us a clean
    schema immediately.

    Once the schema is considered stable, we will introduce Alembic
    and use migrations for PostgreSQL/production.
    """

    SQLModel.metadata.create_all(engine)


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