from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlmodel import Session, select

from src.config import settings
from src.database import get_session
from src.models import User


# ============================================================
# PASSWORD HASHING
# ============================================================

# pwdlib's recommended configuration currently uses a secure
# password-hashing algorithm suitable for application passwords.
#
# Passwords are NEVER stored directly in the database.
password_hash = PasswordHash.recommended()


# ============================================================
# JWT CONFIGURATION
# ============================================================

# JWT configuration is loaded from config.py rather than directly
# from os.environ.
#
# This keeps configuration centralized and makes the application
# easier to test and deploy.
SECRET_KEY = settings.secret_key

ALGORITHM = settings.jwt_algorithm

ACCESS_TOKEN_EXPIRE_MINUTES = (
    settings.access_token_expire_minutes
)


# OAuth2PasswordBearer tells FastAPI where clients obtain their
# access token.
#
# This also enables the "Authorize" button in Swagger UI.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


# ============================================================
# PASSWORD OPERATIONS
# ============================================================


def hash_password(password: str) -> str:
    """
    Hash a plaintext password before storing it.

    The plaintext password should never be persisted or logged.
    """

    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a plaintext password against its stored hash.
    """

    return password_hash.verify(
        plain_password,
        hashed_password,
    )


# ============================================================
# USER AUTHENTICATION
# ============================================================


def authenticate_user(
    session: Session,
    username: str,
    password: str,
) -> User | None:
    """
    Authenticate a user using username and password.

    Returns:
        User: if the credentials are valid.
        None: if authentication fails.

    Authentication failure intentionally returns the same result
    whether the username does not exist or the password is wrong.
    This avoids revealing which usernames exist.
    """

    user = session.exec(
        select(User).where(
            User.username == username,
            User.deleted_at.is_(None),
        )
    ).first()

    if user is None:
        return None

    if not verify_password(
        password,
        user.hashed_password,
    ):
        return None

    return user


# ============================================================
# ACCESS TOKEN CREATION
# ============================================================


def create_access_token(
    user_id: int,
) -> str:
    """
    Create a signed JWT access token for a user.

    The user ID is stored in the standard JWT `sub` (subject)
    claim.

    The token expiration is calculated from the configured
    ACCESS_TOKEN_EXPIRE_MINUTES value.
    """

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# ============================================================
# CURRENT USER
# ============================================================


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    Resolve the currently authenticated user from a JWT.

    Authentication flow:

        Authorization: Bearer <token>
                    ↓
             OAuth2PasswordBearer
                    ↓
               JWT decode
                    ↓
             extract user ID
                    ↓
             database lookup
                    ↓
                User object

    Any invalid or expired token results in HTTP 401.

    A deleted user is also treated as unauthenticated.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        user_id = int(user_id)

    except (
        InvalidTokenError,
        ValueError,
        TypeError,
    ) as exc:

        # Do not expose JWT implementation details to the client.
        raise credentials_exception from exc

    user = session.exec(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    ).first()

    if user is None:
        raise credentials_exception

    return user