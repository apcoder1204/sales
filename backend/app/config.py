import logging
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

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

    CURRENCY: str = "TSh"
    DEFAULT_TIMEZONE: str = "Africa/Dar_es_Salaam"

    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"
    FRONTEND_URL: str = "http://localhost:5173"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 20

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
