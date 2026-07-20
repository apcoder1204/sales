import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.security import (
    verify_password, hash_password, create_access_token, create_refresh_token,
    decode_token, generate_jti,
)
from app.core.exceptions import (
    InvalidCredentialsException, AccountLockedException,
    InactiveUserException, InvalidTokenException, ValidationException,
)
from app.repositories.user_repo import user_repo
from app.repositories.password_reset_repo import password_reset_repo
from app.services.audit_service import audit_service
from app.services.email_service import email_service
from app.schemas.auth import TokenResponse, UserProfile, RefreshRequest, RefreshResponse

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuthService:
    async def login(
        self, db: AsyncSession,
        username: str, password: str, ip: str
    ) -> TokenResponse:
        user = await user_repo.get_by_username(db, username)

        if not user:
            await audit_service.log(
                db, action="LOGIN_FAILED", category="authentication",
                username=username, user_role="unknown",
                details={"reason": "user_not_found", "ip": ip}, ip_address=ip,
            )
            raise InvalidCredentialsException()

        if user.locked_until and user.locked_until > _utcnow():
            raise AccountLockedException(user.locked_until)

        if not verify_password(password, user.password_hash):
            new_attempts = user.failed_login_attempts + 1
            updates = {"failed_login_attempts": new_attempts}
            if new_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                updates["locked_until"] = (
                    _utcnow() + timedelta(minutes=settings.LOCKOUT_MINUTES)
                )
            await user_repo.update(db, user.id, updates)
            await db.commit()
            await audit_service.log(
                db, action="LOGIN_FAILED", category="authentication",
                user_id=user.id, username=user.username, user_role=user.role.name,
                details={"attempts": new_attempts, "ip": ip}, ip_address=ip,
            )
            raise InvalidCredentialsException()

        if not user.is_active:
            raise InactiveUserException()

        refresh_jti = generate_jti()
        await user_repo.update(db, user.id, {
            "failed_login_attempts": 0,
            "locked_until": None,
            "last_login": _utcnow(),
            "last_login_ip": ip,
            "current_refresh_jti": refresh_jti,
        })
        await db.commit()
        await db.refresh(user)

        await audit_service.log(
            db, action="USER_LOGIN", category="authentication",
            user_id=user.id, username=user.username, user_role=user.role.name,
            branch_id=user.branch_id, details={"ip": ip}, ip_address=ip,
        )

        profile = UserProfile(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role.name,
            branch_id=user.branch_id,
            branch=user.branch.name if user.branch else None,
        )
        return TokenResponse(
            access_token=create_access_token(user),
            refresh_token=create_refresh_token(user.id, user.token_version, refresh_jti),
            user=profile,
        )

    async def refresh_token(self, db: AsyncSession, refresh_token: str) -> RefreshResponse:
        from uuid import UUID
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenException()
        user = await user_repo.get_by_id(db, UUID(payload["sub"]))
        if not user or not user.is_active:
            raise InvalidTokenException()
        # Rotation: the presented refresh token must be the one most recently
        # issued to this user, and its embedded token_version must still be
        # current — logout/password-reset bump token_version and clear the
        # stored jti, which instantly invalidates every outstanding refresh
        # token without needing a separate revocation table.
        if payload.get("tv") != user.token_version:
            raise InvalidTokenException()
        if not user.current_refresh_jti or payload.get("jti") != user.current_refresh_jti:
            raise InvalidTokenException()

        new_jti = generate_jti()
        await user_repo.update(db, user.id, {"current_refresh_jti": new_jti})
        await db.commit()

        return RefreshResponse(
            access_token=create_access_token(user),
            refresh_token=create_refresh_token(user.id, user.token_version, new_jti),
        )

    async def logout(self, db: AsyncSession, user) -> None:
        await user_repo.update(db, user.id, {
            "token_version": user.token_version + 1,
            "current_refresh_jti": None,
        })
        await db.commit()
        await audit_service.log(
            db, action="USER_LOGOUT", category="authentication",
            user_id=user.id, username=user.username, user_role=user.role.name,
        )

    async def forgot_password(self, db: AsyncSession, email: str) -> None:
        """Always succeeds from the caller's point of view — never reveals
        whether the email matched an account, to prevent enumeration."""
        user = await user_repo.get_by_email(db, email)
        if not user or not user.is_active:
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = _utcnow() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)

        await password_reset_repo.create(db, {
            "user_id": user.id,
            "token_hash": token_hash,
            "expires_at": expires_at,
        })
        await db.commit()

        await audit_service.log(
            db, action="PASSWORD_RESET_REQUESTED", category="authentication",
            user_id=user.id, username=user.username, user_role=user.role.name,
        )

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        await email_service.send_password_reset(user.email, user.full_name, reset_url)

    async def reset_password(self, db: AsyncSession, token: str, new_password: str) -> None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        reset_token = await password_reset_repo.get_valid_by_hash(db, token_hash)
        if not reset_token:
            await audit_service.log(
                db, action="PASSWORD_RESET_INVALID_TOKEN", category="authentication",
                username="unknown", user_role="unknown",
            )
            raise ValidationException("Kiungo cha kuweka upya nenosiri si sahihi au kimeisha muda")

        user = reset_token.user
        reset_token.used_at = _utcnow()
        await user_repo.update(db, user.id, {
            "password_hash": hash_password(new_password),
            # A password reset should kill every existing session, the same
            # way logout does — otherwise a stolen-and-since-reset account
            # would still be usable via a token minted before the reset.
            "token_version": user.token_version + 1,
            "current_refresh_jti": None,
        })
        await db.flush()
        await db.commit()

        await audit_service.log(
            db, action="PASSWORD_RESET_COMPLETED", category="authentication",
            user_id=user.id, username=user.username, user_role=user.role.name,
        )


auth_service = AuthService()
