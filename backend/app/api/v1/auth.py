from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshRequest, RefreshResponse, UserProfile, UserProfileUpdate,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Uthibitisho"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    return await auth_service.login(db, data.username, data.password, ip)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_token(db, data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, current_user)
    return {"message": "Umetoka mfumoni"}


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.forgot_password(db, data.email)
    # Same response regardless of whether the email matched an account —
    # never reveal which case, to prevent account enumeration.
    return {"me+ssage": "Kama barua pepe hii ipo kwenye mfumo, kiungo cha kuweka upya nenosiri kimetumwa."}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, data.token, data.new_password)
    return {"message": "Nenosiri limebadilishwa. Tafadhali ingia tena."}


@router.get("/me", response_model=UserProfile)
async def me(current_user=Depends(get_current_user)):
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.name,
        branch_id=current_user.branch_id,
        branch=current_user.branch.name if current_user.branch else None,
    )

@router.put("/me", response_model=UserProfile)
async def update_me(
    data: UserProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.security import verify_password, hash_password
    updates = {}
    if data.full_name is not None:
        updates["full_name"] = data.full_name
    if data.email is not None:
        updates["email"] = data.email
    if data.new_password:
        if not data.current_password or not verify_password(data.current_password, current_user.password_hash):
            from app.core.exceptions import ValidationException
            raise ValidationException("Nenosiri la sasa si sahihi")
        updates["password_hash"] = hash_password(data.new_password)
    if updates:
        await db.execute(
            f"""
            UPDATE users SET {', '.join([f'{k} = :{k}' for k in updates.keys()])}, updated_at = CURRENT_TIMESTAMP WHERE id = :id
            """,
            {**updates, "id": str(current_user.id)}
        )
        await db.commit()
        for k, v in updates.items():
            setattr(current_user, k, v)
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.name,
        branch_id=current_user.branch_id,
        branch=current_user.branch.name if current_user.branch else None,
    )
