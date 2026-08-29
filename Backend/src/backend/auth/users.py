from datetime import date

from sqlmodel import Session, select

from backend.models import User
from backend.schemas import UserCreate
from .auth import hash_password


def create_user(session: Session, user_data: UserCreate) -> User:
    existing_user = session.exec(
        select(User).where(
            User.username == user_data.username,
            User.deleted_at.is_(None)
        )
    ).first()

    if existing_user:
        raise ValueError("Username already exists")

    user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        weight=user_data.weight,
        height=user_data.height,
        birthdate=user_data.birthdate,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def get_user(session: Session, user_id: int) -> User | None:
    return session.exec(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None)
        )
    ).first()


def get_user_by_username(
    session: Session,
    username: str
) -> User | None:

    return session.exec(
        select(User).where(
            User.username == username,
            User.deleted_at.is_(None)
        )
    ).first()


def calculate_age(birthdate: date) -> int:
    today = date.today()

    age = today.year - birthdate.year

    if (today.month, today.day) < (
        birthdate.month,
        birthdate.day
    ):
        age -= 1

    return age