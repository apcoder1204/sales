import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from jose import jwt, JWTError, ExpiredSignatureError
from pydantic_core import PydanticCustomError
import bcrypt
from app.config import settings

UTC = timezone.utc


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# A password matching one of these (case-insensitive, ignoring trailing
# digits/punctuation people tack on to satisfy a strength meter) is rejected
# outright regardless of otherwise passing the character-class checks below
# — "Password123" and "Admin123!" both pass every rule above but are still
# among the first guesses in any real attack.
_DENYLISTED_PASSWORDS = {
    "password", "password1", "password123", "admin", "admin123",
    "letmein", "letmein1", "welcome", "welcome1", "qwerty", "qwerty123",
    "12345678", "123456789", "changeme", "changeme1",
}


def validate_password_strength(password: str) -> str:
    """Shared by every schema that accepts a new password (user create/update,
    password reset) so the policy can't drift between call sites.

    Raises PydanticCustomError (not plain ValueError) so each failure gets a
    stable `type` (e.g. "password_too_short") in the resulting validation
    error instead of a generic "value_error" — that stable type is what the
    frontend maps to a translated message (see makosa.uthibitisho in
    en.js/sw.js), the same way `code` does for AppException."""
    if len(password) < 8:
        raise PydanticCustomError("password_too_short", "Nenosiri lazima liwe na herufi angalau 8")
    if len(password.encode("utf-8")) > 72:
        raise PydanticCustomError("password_too_long", "Nenosiri ni refu mno")
    if not re.search(r"[a-z]", password):
        raise PydanticCustomError("password_needs_lowercase", "Nenosiri lazima liwe na angalau herufi ndogo moja")
    if not re.search(r"[A-Z]", password):
        raise PydanticCustomError("password_needs_uppercase", "Nenosiri lazima liwe na angalau herufi kubwa moja")
    if not re.search(r"\d", password):
        raise PydanticCustomError("password_needs_digit", "Nenosiri lazima liwe na angalau namba moja")
    normalized = re.sub(r"[\d\W]+$", "", password.strip().lower())
    if normalized in _DENYLISTED_PASSWORDS:
        raise PydanticCustomError("password_too_common", "Nenosiri hili ni rahisi kubashiri sana, chagua lingine")
    return password


def generate_jti() -> str:
    return secrets.token_urlsafe(24)


def create_access_token(user) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.name,
        "branch_id": str(user.branch_id) if user.branch_id else None,
        "type": "access",
        "tv": user.token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: UUID, token_version: int, jti: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "tv": token_version,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    from app.core.exceptions import TokenExpiredException, InvalidTokenException
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError:
        raise TokenExpiredException()
    except JWTError:
        raise InvalidTokenException()
