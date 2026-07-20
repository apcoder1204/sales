from uuid import UUID
from datetime import datetime, timezone
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import decode_token
from app.core.exceptions import (
    InvalidTokenException, InactiveUserException,
    AccountLockedException, InsufficientPermissionException,
)

UTC = timezone.utc

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.user_repo import user_repo

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise InvalidTokenException()

    user = await user_repo.get_by_id(db, UUID(payload["sub"]))
    if not user or not user.is_active:
        raise InactiveUserException()
    if user.locked_until and user.locked_until > datetime.now(UTC).replace(tzinfo=None):
        raise AccountLockedException(user.locked_until)
    # Logout / password reset bump token_version — any token minted before
    # that point (access or refresh) must stop working immediately, not just
    # at its natural expiry.
    if payload.get("tv") != user.token_version:
        raise InvalidTokenException()
    return user


def require_role(*roles: str):
    async def checker(
        request: Request,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        if current_user.role.name not in roles:
            from app.services.audit_service import audit_service
            await audit_service.log(
                db, action="PERMISSION_DENIED", category="system",
                user_id=current_user.id, username=current_user.username,
                user_role=current_user.role.name,
                details={
                    "path": request.url.path, "method": request.method,
                    "required_roles": list(roles),
                },
                ip_address=request.client.host if request.client else None,
            )
            raise InsufficientPermissionException()
        return current_user
    return checker


# Pre-built role shortcuts used across routers
require_super_admin = require_role("super_admin")
require_admin = require_role("super_admin", "admin")
require_manager = require_role("super_admin", "admin", "general_manager")
require_storekeeper = require_role("super_admin", "admin", "store_keeper", "general_manager")
require_cashier_access = require_role("super_admin", "admin", "cashier")
