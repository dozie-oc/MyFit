from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration.

    Values are loaded from environment variables and/or the local
    .env file.

    Other modules should import `settings` from this module instead
    of calling os.getenv() directly. This keeps configuration in
    one place and makes the application easier to test and deploy.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================================
    # DATABASE
    # ============================================================

    # SQLite is used during local development because the database
    # can be deleted and recreated whenever the schema changes.
    #
    # When the application is ready for production, this value can
    # be replaced with a PostgreSQL connection URL without requiring
    # changes to the application-level database logic.
    database_url: str = "sqlite:///./myfit.db"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """
        Ensure that a supported database URL has been supplied.

        SQLite is the current development database.
        PostgreSQL is supported for the eventual production setup.
        """

        value = value.strip()

        if not value:
            raise ValueError(
                "DATABASE_URL cannot be empty."
            )

        if not (
            value.startswith("sqlite://")
            or value.startswith("postgresql://")
            or value.startswith("postgres://")
        ):
            raise ValueError(
                "DATABASE_URL must use SQLite or PostgreSQL."
            )

        return value

    # ============================================================
    # JWT / AUTHENTICATION
    # ============================================================

    # The JWT signing secret MUST come from the environment.
    #
    # There is intentionally no default value. The application
    # should fail during startup rather than accidentally running
    # with a predictable signing key.
    secret_key: str = Field(
        min_length=32,
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        """Reject an empty or whitespace-only JWT secret."""

        value = value.strip()

        if not value:
            raise ValueError(
                "SECRET_KEY cannot be empty."
            )

        return value

    # HS256 is appropriate for the current MVP because this
    # application both creates and verifies its own JWTs.
    #
    # If authentication is later split across multiple services,
    # asymmetric signing such as RS256 or ES256 can be considered.
    jwt_algorithm: str = "HS256"

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        """
        Restrict the configured JWT algorithm to the algorithm
        currently supported by auth.py.
        """

        value = value.strip().upper()

        if value != "HS256":
            raise ValueError(
                "JWT_ALGORITHM must be HS256."
            )

        return value

    # Access tokens are deliberately short-lived.
    #
    # A future production version could introduce refresh tokens
    # rather than making access tokens excessively long-lived.
    access_token_expire_minutes: int = Field(
        default=10080,
        gt=0,
        le=43200,
    )

    # ============================================================
    # USDA FOODDATA CENTRAL
    # ============================================================

    # The USDA API key is required.
    #
    # We intentionally do not fall back to DEMO_KEY. The application
    # should fail at startup if the required external-service
    # configuration has not been provided.
    usda_api_key: str = Field(
        min_length=1,
    )

    @field_validator("usda_api_key")
    @classmethod
    def validate_usda_api_key(cls, value: str) -> str:
        """Reject an empty or whitespace-only USDA API key."""

        value = value.strip()

        if not value:
            raise ValueError(
                "USDA_API_KEY cannot be empty."
            )

        return value

    # USDA FoodData Central API base URL.
    usda_base_url: str = (
        "https://api.nal.usda.gov/fdc/v1"
    )

    # Maximum amount of time the application will wait for USDA
    # to respond before treating the request as failed.
    usda_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Load and cache application settings.

    Pydantic Settings automatically reads:
        1. Environment variables
        2. Values from the configured .env file

    Caching means the configuration is parsed only once per
    application process.
    """

    return Settings()


# Single application-wide settings instance.
#
# Other modules should use:
#
#     from backend.config import settings
#
# instead of accessing environment variables directly.
settings = get_settings()