from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.security import (
    verify_password, create_access_token, create_refresh_token, decode_token, generate_jti,
)
from app.core.exceptions import (
    InvalidCredentialsException, AccountLockedException,
    InactiveUserException, InvalidTokenException
)
from app.repositories.user_repo import user_repo
from app.services.audit_service import audit_service
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


auth_service = AuthService()
