from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from src.auth.auth import get_current_user
from src.database import get_session
from src.models import User


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

# Provides a SQLModel Session to any route that needs database
# access.
#
# Usage:
#
#     def some_route(
#         session: SessionDep,
#     ):
#         ...
#
# FastAPI automatically calls get_session() and injects the
# resulting Session into the route.
SessionDep = Annotated[
    Session,
    Depends(get_session),
]


# ============================================================
# AUTHENTICATED USER DEPENDENCY
# ============================================================

# Provides the currently authenticated User to protected routes.
#
# get_current_user() is responsible for:
#
#     1. Reading the JWT from the request.
#     2. Validating the token.
#     3. Resolving the user from the database.
#     4. Rejecting unauthenticated/invalid requests.
#
# This keeps authentication logic out of individual routers.
#
# Usage:
#
#     def some_route(
#         current_user: CurrentUserDep,
#     ):
#         ...
#
CurrentUserDep = Annotated[
    User,
    Depends(get_current_user),
]