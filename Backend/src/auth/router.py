from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from src.auth.auth import (
    authenticate_user,
    create_access_token,
    hash_password,
)
from src.dependencies import CurrentUserDep, SessionDep
from src.models import User
from src.schemas import (
    Token,
    UserAuth,
    UserCreate,
    UserOut,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ============================================================
# USER REGISTRATION
# ============================================================


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    session: SessionDep,
):
    """
    Register a new user.

    Passwords are hashed before being stored.

    Usernames are normalized to lowercase and surrounding
    whitespace is removed so authentication is consistent.
    """

    username = user_data.username.strip().lower()

    # Check for an existing active user.
    #
    # We use case-insensitive comparison here because usernames
    # are normalized to lowercase when stored.
    existing_user = session.exec(
        select(User).where(
            User.username == username,
            User.deleted_at.is_(None),
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=username,
        hashed_password=hash_password(
            user_data.password,
        ),
        weight=user_data.weight,
        height=user_data.height,
        birthdate=user_data.birthdate,
    )

    session.add(user)

    try:
        session.commit()

    except IntegrityError as exc:
        # Roll the transaction back before returning an error.
        #
        # This also protects us against a race condition where
        # another request creates the same username between the
        # existence check and the commit.
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from exc

    session.refresh(user)

    return UserOut(
        id=user.id,
        username=user.username,
        weight=user.weight,
        height=user.height,
        birthdate=user.birthdate,
        age=calculate_age(user.birthdate),
    )


# ============================================================
# LOGIN
# ============================================================


@router.post(
    "/login",
    response_model=Token,
)
def login(
    credentials: UserAuth,
    session: SessionDep,
):
    """
    Authenticate a user and issue a JWT access token.
    """

    username = credentials.username.strip().lower()

    user = authenticate_user(
        session,
        username,
        credentials.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    access_token = create_access_token(
        user.id,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


# ============================================================
# CURRENT USER
# ============================================================


@router.get(
    "/me",
    response_model=UserOut,
)
def get_me(
    current_user: CurrentUserDep,
):
    """
    Return the currently authenticated user's profile.
    """

    return UserOut(
        id=current_user.id,
        username=current_user.username,
        weight=current_user.weight,
        height=current_user.height,
        birthdate=current_user.birthdate,
        age=calculate_age(
            current_user.birthdate,
        ),
    )


# ============================================================
# HELPERS
# ============================================================


def calculate_age(
    birthdate: date,
) -> int:
    """
    Calculate a user's current age from their birthdate.

    Age is calculated dynamically rather than stored in the
    database because it changes automatically over time.
    """

    today = date.today()

    age = today.year - birthdate.year

    if (
        today.month,
        today.day,
    ) < (
        birthdate.month,
        birthdate.day,
    ):
        age -= 1

    return age