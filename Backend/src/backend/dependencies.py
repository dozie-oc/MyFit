from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from .database import get_session
from .auth.auth import get_current_user
from .models import User


SessionDep = Annotated[
    Session,
    Depends(get_session)
]


CurrentUserDep = Annotated[
    User,
    Depends(get_current_user)
]