import logging
import os
import time
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Every "UTC now" timestamp in this codebase (see the several local
# `_utcnow()` helpers in app/services/*.py) is a *naive* datetime — built by
# stripping tzinfo off an aware UTC value, then written straight into
# TIMESTAMPTZ columns. asyncpg encodes a naive datetime parameter using the
# *process's* local system timezone, not the Postgres session's — so on any
# host whose OS timezone isn't already UTC (e.g. this app's own
# DEFAULT_TIMEZONE, Africa/Dar_es_Salaam), every such write/comparison would
# silently be off by that host's UTC offset. Forcing the process itself to
# UTC, as early as possible (this module is imported before any DB code),
# makes asyncpg's assumption match the convention every naive timestamp in
# this codebase already relies on.
os.environ["TZ"] = "UTC"
if hasattr(time, "tzset"):
    time.tzset()

logger = logging.getLogger("dukani.config")

_DEV_SECRET = "dev-secret-key-change-in-production-minimum-32chars"


class Settings(BaseSettings):
    APP_NAME: str = "DUKANI POS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    DATABASE_URL: str = "postgresql+asyncpg://dukani:dukani_secret@localhost:5432/dukani_pos"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    SECRET_KEY: str = _DEV_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    BCRYPT_ROUNDS: int = 12

    CORS_ORIGINS: List[str] = ["*"]

    # Off by default — the current deployment serves plain HTTP with no
    # domain/TLS yet. Flip on once certbot/TLS is in place (see DEPLOYMENT.md).
    ENABLE_HSTS: bool = False

    CURRENCY: str = "TSh"
    DEFAULT_TIMEZONE: str = "Africa/Dar_es_Salaam"

    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"
    FRONTEND_URL: str = "http://localhost:5173"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 20

    # Rate limiting uses in-process memory only (see core/rate_limit.py) —
    # not shared across workers, resets on restart, but has no external
    # dependency.
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_DEFAULT: str = "100/minute"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    @model_validator(mode="after")
    def warn_insecure_defaults(self) -> "Settings":
        if self.SECRET_KEY == _DEV_SECRET:
            logger.warning(
                "SECRET_KEY is using the insecure development default. "
                "Set SECRET_KEY in your .env file before deploying to production."
            )
        if "*" in self.CORS_ORIGINS:
            logger.warning(
                "CORS_ORIGINS contains '*' (all origins allowed). "
                "Restrict this to specific domains in production."
            )
        if not self.RESEND_API_KEY:
            logger.warning(
                "RESEND_API_KEY is not set — password reset emails will fail to send."
            )
        return self


settings = Settings()
