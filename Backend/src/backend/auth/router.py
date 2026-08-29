from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from backend.dependencies import SessionDep
from backend.models import User
from backend.schemas import (
    Token,
    UserAuth,
    UserCreate,
    UserOut,
)

from backend.auth.auth import (
    authenticate_user,
    create_access_token,
    hash_password,
)
from backend.auth.auth import get_current_user
from fastapi import Depends


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserCreate,
    session: SessionDep
):

    existing_user = session.exec(
        select(User).where(
            User.username == user_data.username,
            User.deleted_at.is_(None)
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )

    user = User(
        username=user_data.username,
        hashed_password=hash_password(
            user_data.password
        ),
        weight=user_data.weight,
        height=user_data.height,
        birthdate=user_data.birthdate
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "weight": user.weight,
        "height": user.height,
        "birthdate": user.birthdate,
        "age": calculate_age(user.birthdate)
    }


@router.post(
    "/login",
    response_model=Token
)
def login(
    credentials: UserAuth,
    session: SessionDep
):

    user = authenticate_user(
        session,
        credentials.username,
        credentials.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    access_token = create_access_token(
        user.id
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get(
    "/me",
    response_model=UserOut
)
def get_me(
    current_user: CurrentUserDep
):

    return {
        "id": current_user.id,
        "username": current_user.username,
        "weight": current_user.weight,
        "height": current_user.height,
        "birthdate": current_user.birthdate,
        "age": calculate_age(
            current_user.birthdate
        )
    }


def calculate_age(birthdate: date) -> int:

    today = date.today()

    age = today.year - birthdate.year

    if (
        today.month,
        today.day
    ) < (
        birthdate.month,
        birthdate.day
    ):
        age -= 1

    return age