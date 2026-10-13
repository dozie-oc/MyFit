"""
Shared pytest configuration and helpers.

Each test module keeps its own isolated in-memory database (so state can
never leak between modules), but the engine construction boilerplate
lives here instead of being copy-pasted into every file.
"""

import sys
from pathlib import Path

from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

# Make the project root importable (pyproject also sets pythonpath).
backend_root = Path(__file__).resolve().parent.parent

if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def make_test_engine():
    """Create an isolated in-memory SQLite engine for a test module."""

    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
